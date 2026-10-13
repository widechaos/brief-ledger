import copy
import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from ledger import Reviewer, validate_rows
from server import make_handler

SAMPLE = json.loads((Path(__file__).parents[1]/'web/sample.json').read_text())

class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviewer=Reviewer()

    def test_paraphrase_and_quantity_increase(self):
        result=self.reviewer.analyze(SAMPLE)
        r=result['results'][0]
        self.assertEqual(r['candidates'][0]['source']['id'],'B2')
        self.assertEqual(r['signal'],'Related deliverable')
        self.assertEqual(r['quantity_delta'],2)

    def test_original_evidence_and_ids_preserved(self):
        r=self.reviewer.analyze(SAMPLE)['results'][0]
        self.assertEqual(r['request']['text'],SAMPLE['requests'][0]['text'])
        self.assertEqual(r['candidates'][0]['source']['text'],SAMPLE['brief'][1]['text'])

    def test_unit_mismatch_never_subtracts(self):
        payload=copy.deepcopy(SAMPLE);payload['requests'][0]['unit']='hour'
        self.assertIsNone(self.reviewer.analyze(payload)['results'][0]['quantity_delta'])

    def test_duplicate_sources_are_ambiguous(self):
        payload=copy.deepcopy(SAMPLE);payload['brief']=[payload['brief'][1]]*2
        r=self.reviewer.analyze(payload)['results'][0]
        self.assertEqual(r['signal'],'Ambiguous match')
        self.assertIsNone(r['quantity_delta'])

    def test_unrelated_request_abstains(self):
        r=self.reviewer.analyze(SAMPLE)['results'][2]
        self.assertEqual(r['signal'],'No clear match')
        self.assertIsNone(r['quantity_delta'])

    def test_validation_rejects_empty_overflow_and_invalid_counts(self):
        for rows in [[],[SAMPLE['brief'][0]]*21,[{'text':'x'*501,'quantity':1,'unit':'page'}],[{'text':'Valid copy','quantity':True,'unit':'page'}],[{'text':'Valid copy','quantity':0,'unit':'page'}]]:
            with self.assertRaises(ValueError): validate_rows(rows,'brief')

    def test_host_origin_json_and_traversal_guards(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.reviewer,0));port=server.server_port
        server.RequestHandlerClass=make_handler(self.reviewer,port)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def req(method,path,headers,body=None):
            conn=HTTPConnection('127.0.0.1',port);conn.request(method,path,body,headers);res=conn.getresponse();res.read();conn.close();return res.status
        host=f'127.0.0.1:{port}'
        try:
            self.assertEqual(req('GET','/',{'Host':'evil.example'}),403)
            self.assertEqual(req('GET','/../ledger.py',{'Host':host}),404)
            self.assertEqual(req('POST','/api/review',{'Host':host,'Origin':'https://evil.example','Content-Type':'application/json'},'{}'),403)
            self.assertEqual(req('POST','/api/review',{'Host':host,'Origin':'http://'+host,'Content-Type':'application/json'},'{'),400)
            self.assertEqual(req('POST','/api/review',{'Host':host,'Origin':'http://'+host,'Content-Type':'application/json'},json.dumps(SAMPLE)),200)
        finally: server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
