from io import StringIO
import unittest

from tools.tracecmp import compare


def cap(rows):
    return StringIO('time,D0,ACK\n' + rows)


class TraceComparison(unittest.TestCase):
    def test_alignment_and_ignored_channel(self):
        self.assertEqual(compare(cap('0,0,1\n1,0,0\n2,1,1'),
                                 cap('5,0,0\n12,1,0'), ['D0']), (2, None))

    def test_missing_last_edge(self):
        count, (left, right) = compare(cap('0,0,1\n1,0,0'), cap('0,0,1'), ['ACK'])
        self.assertEqual((count, left[1], right), (1, '0', None))

    def test_bad_levels_and_time(self):
        for rows in ('1,2,1', '1,1,0\n0,1,1', ''):
            with self.assertRaises(ValueError):
                compare(cap(rows), cap('0,1,0'), ['D0'])
