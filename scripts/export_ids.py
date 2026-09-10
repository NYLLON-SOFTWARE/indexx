#!/usr/bin/env python3
"""Normalize scoped Instagram Saved grid batches; no network or browser access."""
import argparse
import csv
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

HOSTS = {'instagram.com', 'www.instagram.com'}
SOURCE = re.compile(r'^/([A-Za-z0-9._]+)/saved/all-posts/?$')
MEDIA = re.compile(r'^/(p|reel|reels|tv)/([A-Za-z0-9_-]+)/?$')
STORY = re.compile(r'^/stories/([A-Za-z0-9._]+)/(\d+)/?$')


def parse_item(raw, base):
    if not isinstance(raw, dict) or not isinstance(raw.get('url'), str):
        return None
    try:
        u = urlsplit(urljoin(base, raw['url']))
        if u.scheme != 'https' or u.netloc.lower() not in HOSTS:
            return None
    except ValueError:
        return None
    badges = raw.get('badges', [])
    badges = sorted({b for b in badges if isinstance(b, str)}) if isinstance(badges, list) else []
    m = MEDIA.fullmatch(u.path)
    if m:
        route, code = m.groups()
        kind = 'reel' if route in ('reel', 'reels') or 'Clip' in badges else 'carousel' if 'Carousel' in badges else 'video' if route == 'tv' else 'post_or_reel'
        return {'id': code, 'id_kind': 'shortcode', 'media_id': None,
                'type': kind, 'url': f'https://www.instagram.com/{route}/{code}/', 'badges': badges}
    m = STORY.fullmatch(u.path)
    if m and m[1].lower() != 'highlights':
        return {'id': m[2], 'id_kind': 'story_id', 'media_id': None,
                'type': 'story', 'url': f'https://www.instagram.com/stories/{m[1]}/{m[2]}/', 'badges': badges}
    return None


def normalize(batches, status, reason):
    items, unresolved, times, accounts, sources = {}, [], [], set(), set()
    for number, batch in enumerate(batches, 1):
        source = batch.get('source_url', '')
        u = urlsplit(source)
        m = SOURCE.fullmatch(u.path)
        if u.scheme != 'https' or u.netloc.lower() not in HOSTS or not m:
            raise ValueError(f'Batch {number}: source must be an Instagram /USERNAME/saved/all-posts/ URL')
        accounts.add(m[1].lower())
        sources.add(f'https://www.instagram.com/{m[1]}/saved/all-posts/')
        if len(accounts) > 1:
            raise ValueError('Mixed-account checkpoints are not supported')
        if not isinstance(batch.get('captured_at'), str) or not batch['captured_at']:
            raise ValueError(f'Batch {number}: captured_at is required')
        times.append(batch['captured_at'])
        if not isinstance(batch.get('links'), list):
            raise ValueError(f'Batch {number}: links must be a list')
        for raw in batch['links']:
            item = parse_item(raw, source)
            if item is None:
                unresolved.append({'batch': number, 'link': raw})
                continue
            key = f"{item['id_kind']}:{item['id']}"
            if key not in items:
                items[key] = {**item, 'observed_urls': [item['url']], 'observed_types': [item['type']]}
            else:
                old = items[key]
                old['observed_urls'] = sorted(set(old['observed_urls'] + [item['url']]))
                old['badges'] = sorted(set(old['badges'] + item['badges']))
                old['observed_types'] = sorted(set(old['observed_types'] + [item['type']]))
                known = set(old['observed_types']) - {'post_or_reel'}
                old['type'] = next(iter(known)) if len(known) == 1 else 'unknown' if known else 'post_or_reel'
    if not times:
        raise ValueError('No checkpoint batches supplied')
    if status == 'empty' and (items or unresolved):
        raise ValueError('An empty capture cannot contain items or unresolved links')
    return {'source_urls': sorted(sources), 'captured_from': times[0], 'captured_to': times[-1],
            'coverage': {'status': status, 'reason': reason, 'server_total_verified': False},
            'batch_count': len(times), 'unique_count': len(items),
            'unresolved_links': unresolved, 'items': list(items.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoints', type=Path)
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--status', choices=['partial', 'end-observed', 'empty'], default='partial')
    parser.add_argument('--reason', required=True)
    args = parser.parse_args()
    try:
        batches = [json.loads(line) for line in args.checkpoints.read_text(encoding='utf-8').splitlines() if line.strip()]
        result = normalize(batches, args.status, args.reason)
    except (ValueError, TypeError, AttributeError, OSError) as e:
        parser.error(str(e))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / 'saved-items.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    fields = ['id', 'id_kind', 'media_id', 'type', 'url']
    with (args.out_dir / 'saved-items.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(result['items'])
    (args.out_dir / 'saved-ids.txt').write_text(''.join(f"{i['id']}\n" for i in result['items']), encoding='utf-8')
    print(json.dumps({'unique_count': result['unique_count'], 'unresolved_count': len(result['unresolved_links']), 'status': args.status}))


if __name__ == '__main__':
    main()
