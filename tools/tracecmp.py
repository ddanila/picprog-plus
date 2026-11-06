#!/usr/bin/env python3
"""Compare digital transitions from two timestamped CSVs. GPL-2.0-only."""
import argparse
import csv
from decimal import Decimal, InvalidOperation
from itertools import zip_longest


def transitions(stream, names):
    rows = csv.DictReader(stream)
    fields = rows.fieldnames or []
    if any(fields.count(n) != 1 for n in ['time', *names]):
        raise ValueError('expected unique time and requested channel headers')
    last_time = None
    last_bits = None
    for row in rows:
        try:
            t = Decimal(row['time'])
            bits = ''.join(row[n] for n in names)
        except (InvalidOperation, TypeError) as exc:
            raise ValueError(f'invalid sample on line {rows.line_num}') from exc
        if (not t.is_finite() or (last_time is not None and t < last_time)
                or any(row[n] not in ('0', '1') for n in names)):
            raise ValueError(f'invalid sample on line {rows.line_num}')
        if bits != last_bits:
            yield t, bits
        last_time, last_bits = t, bits
    if last_time is None:
        raise ValueError('empty capture')


def compare(a, b, names):
    count = 0
    for left, right in zip_longest(transitions(a, names), transitions(b, names)):
        if left is None or right is None or left[1] != right[1]:
            return count, (left, right)
        count += 1
    return count, None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('first', type=argparse.FileType('r'))
    p.add_argument('second', type=argparse.FileType('r'))
    p.add_argument('channels', nargs='+')
    args = p.parse_args()
    if 'time' in args.channels or len(set(args.channels)) != len(args.channels):
        p.error('channels must be distinct digital columns')
    try:
        count, diff = compare(args.first, args.second, args.channels)
    except ValueError as exc:
        p.error(str(exc))
    if diff:
        print(f'{count} matching states; first difference (time, bits): {diff}')
        return 1
    print(f'{count} states match in order (timing not compared)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
