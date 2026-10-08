"""Regression tests for sparse video scans and VALORANT-only gating (offline)."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from analyze import (is_valorant_gameplay, is_collection, match_skin, segments,
                     scan_video, PROBE_INTERVAL_SECONDS, DETAIL_INTERVAL_SECONDS)
from discover import clean_entry, canonical_video_url

VIDEO = SimpleNamespace(player='TenZ',
                        url='https://www.youtube.com/watch?v=abcdefghijk',
                        title='ranked stream', duration=600)
CATALOG = {'Prime Vandal':'Vandal', 'Reaver Phantom':'Phantom'}

class ScannerTests(unittest.TestCase):
    def test_hud_filters_unrelated_game(self):
        self.assertTrue(is_valorant_gameplay('BUY PHASE 0:30'))
        self.assertTrue(is_valorant_gameplay('DEFENDERS  SPIKE  VANDAL'))
        self.assertFalse(is_valorant_gameplay('playing minecraft with friends'))
        self.assertFalse(is_valorant_gameplay('here is my Vandal skin'))
        self.assertFalse(is_valorant_gameplay('COUNTER STRIKE CS2 COMPETITIVE'))
        self.assertTrue(is_collection('COLLECTION VANDAL'))

    def test_samples_spread_across_long_stream(self):
        windows=segments(3 * 60 * 60)
        self.assertGreaterEqual(len(windows), 3)
        self.assertEqual(windows[0][0], 0)
        self.assertEqual(windows[-1][1], 3 * 60 * 60)
        self.assertTrue(all(stop-start<=150 for start,stop in windows))
        self.assertEqual(segments(90),[(0,90)])

    def test_missing_duration_has_bounded_samples(self):
        windows=segments(None)
        self.assertLessEqual(len(windows), 5)
        self.assertTrue(all(b-a<=150 for a,b in windows))

    def test_skips_other_games_without_detail_scan(self):
        calls=[]
        def getter(url,start,stop,work,*,interval,prefix):
            calls.append((prefix,interval))
            if prefix!='probe':
                raise AssertionError('Never inspect an unrelated game's detailed frames')
            return [Path('/tmp/probe_0001.jpg')]
        with patch('analyze.read_frame_text',return_value='minecraft house build'):
            result=scan_video(VIDEO,CATALOG,getter=getter)
        self.assertEqual(result['status'],'no_valorant')
        self.assertFalse(result['valorant_seen'])
        self.assertEqual(result['skipped_non_valorant_segments'],len(segments(VIDEO.duration)))
        self.assertTrue(all(name=='probe' for name,_ in calls))

    def test_detects_valorant_then_two_collection_frames(self):
        calls=[]
        def getter(url,start,stop,work,*,interval,prefix):
            calls.append((prefix,interval))
            if prefix=='probe':
                return [work/'probe_0001.jpg']
            return [work/'detail_0001.jpg',work/'detail_0002.jpg',
                    work/'detail_0003.jpg']
        def text_from_fake_frame(frame):
            if frame.name.startswith('probe'): return 'BUY PHASE 0:15'
            return 'COLLECTION Prime Vandal'
        with patch('analyze.read_frame_text',side_effect=text_from_fake_frame):
            result=scan_video(VIDEO,CATALOG,getter=getter)
        self.assertEqual(result['status'],'verified')
        self.assertTrue(result['valorant_seen'])
        self.assertTrue(result['collection_seen'])
        self.assertEqual(result['candidates'][0]['skin'],'Prime Vandal')
        self.assertEqual(result['candidates'][0]['hits'],2)
        self.assertEqual([x[0] for x in calls],['probe','detail'])
        self.assertEqual([x[1] for x in calls],
                         [PROBE_INTERVAL_SECONDS,DETAIL_INTERVAL_SECONDS])

    def test_gameplay_without_collection_has_no_fake_skin(self):
        def getter(url,start,stop,work,*,interval,prefix):
            return [work/(prefix+'_0001.jpg')]
        def scan_text(path):
            return 'BUY PHASE  DEFENDERS' if path.name.startswith('probe') else 'SCOREBOARD'
        with patch('analyze.read_frame_text',side_effect=scan_text):
            result=scan_video(VIDEO,CATALOG,getter=getter)
        self.assertEqual(result['status'],'valorant_no_collection')
        self.assertEqual(result['candidates'],[])

    def test_requires_two_independent_frames(self):
        def getter(url,start,stop,work,*,interval,prefix):
            return [work/(prefix+'_0001.jpg')]
        def text_for(path):
            return 'BUY PHASE' if path.name.startswith('probe') else 'COLLECTION Reaver Phantom'
        with patch('analyze.read_frame_text',side_effect=text_for):
            result=scan_video(VIDEO,CATALOG,getter=getter)
        self.assertEqual(result['status'],'verified' if len(segments(VIDEO.duration))>1 else 'candidate_found')
        # Multiple distinct sampled sections count as distinct video frames.
        self.assertNotEqual(result['candidates'],[])

class DiscoveryTests(unittest.TestCase):
    def test_refuses_twitch_channel_playlist_as_vod(self):
        fake={'id':'aspaszin','url':'https://www.twitch.tv/aspaszin/videos?filter=archives&sort=time',
              'title':'Past Broadcasts'}
        self.assertIsNone(clean_entry('aspas','https://www.twitch.tv/aspaszin/videos',fake))

    def test_real_twitch_vod(self):
        entry={'id':'v2894146974','url':'https://www.twitch.tv/videos/2894146974',
               'title':'Ranked','duration':7200}
        result=clean_entry('TenZ','https://www.twitch.tv/tenz/videos',entry)
        self.assertEqual(result.url,'https://www.twitch.tv/videos/2894146974')

    def test_youtube_video_id(self):
        entry={'id':'abcdefghijk','url':'abcdefghijk','duration':3600}
        self.assertEqual(canonical_video_url('youtube',entry),
                         'https://www.youtube.com/watch?v=abcdefghijk')

if __name__=='__main__':
    unittest.main()
