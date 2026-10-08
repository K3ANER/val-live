import os, threading, unittest
from unittest.mock import patch
from backend.scan import scan, agreed, validate_url, ScanError
from backend.app import app
ROW={'weapon':'Vandal','skin':'Prime Vandal','skinId':'test-id','icon':'https://media.valorant-api.com/reference.png'}
ROWS={('Vandal','prime vandal'):ROW}
COLLECTION={'collection':True,'equipped_loadout':True,'evidence':'equipment overview','skins':[{'weapon':'Vandal','skin':'Prime Vandal','certain':True}]}
class FakeVision:
    def __init__(self,results,valid=True): self.results=iter(results);self.valid=valid;self.calls=0
    def detect(self,frame): self.calls+=1;return next(self.results)
    def verify(self,*args): self.calls+=1;return {'matches':self.valid,'equipped':self.valid,'evidence':'matching geometry'}
class FakeFrames:
    def __init__(self,source): self.closed=False;self.reads=0
    def __enter__(self): return self
    def next(self):
        if self.closed: raise AssertionError('Read after stop')
        self.reads+=1;return (self.reads*5,b'test-frame')
    def close(self): self.closed=True
    def __exit__(self,*args): self.close()
class ScanTests(unittest.TestCase):
    def run_scan(self,vision,event=None):
        self.frames=FakeFrames({})
        return scan({},lambda *args:None,event or threading.Event(),vision,ROWS,lambda _:self.frames)
    def test_stop_before_third_frame(self):
        r=self.run_scan(FakeVision([COLLECTION,COLLECTION]));self.assertEqual(r['status'],'completed');self.assertEqual(self.frames.reads,2);self.assertTrue(self.frames.closed)
    def test_mismatch_not_published(self):
        r=self.run_scan(FakeVision([COLLECTION,COLLECTION],False));self.assertEqual(r['status'],'collection_unverified');self.assertFalse(r['weapons'])
    def test_gameplay_resets_confirmation(self):
        r=self.run_scan(FakeVision([COLLECTION,{'collection':False},COLLECTION,COLLECTION]));self.assertEqual(self.frames.reads,4);self.assertEqual(r['status'],'completed')
    def test_unknown_and_uncertain_rejected(self):
        u={**COLLECTION,'skins':[{'weapon':'Vandal','skin':'Prime Vandal','certain':False}]};self.assertEqual(agreed(COLLECTION,u,ROWS),[]);self.assertEqual(agreed(COLLECTION,COLLECTION,{}),[])
    def test_cancel_reads_no_frames(self):
        e=threading.Event();e.set();r=self.run_scan(FakeVision([]),e);self.assertEqual(r['status'],'cancelled');self.assertEqual(self.frames.reads,0)
    def test_url_validation(self):
        for u in ['http://youtube.com','https://localhost','https://youtube.com.evil.test','https://user:pass@youtube.com','https://youtube.com:444']:
            with self.assertRaises(ScanError): validate_url(u)
        self.assertEqual(validate_url('https://youtu.be/abc'),'https://youtu.be/abc')
    def test_endpoints_require_token(self):
        with patch.dict(os.environ,{'SCAN_TOKEN':'private-test'}):
            c=app.test_client();self.assertEqual(c.post('/api/analyze',json={}).status_code,401);self.assertEqual(c.post('/api/cancel').status_code,401)
    def test_cors_allowlist(self):
        c=app.test_client();self.assertNotIn('Access-Control-Allow-Origin',c.get('/api/health',headers={'Origin':'https://evil.test'}).headers);self.assertEqual(c.get('/api/health',headers={'Origin':'https://k3aner.github.io'}).headers['Access-Control-Allow-Origin'],'https://k3aner.github.io')
if __name__=='__main__': unittest.main()
