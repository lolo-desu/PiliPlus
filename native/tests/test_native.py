from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nativeapp.storage import Store
from nativeapp.services import Service, sign


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store=Store('test',self.temp.name)

    def test_export_excludes_credentials_and_round_trips(self):
        self.store.set('theme','dark');self.store.set('cookie','secret')
        self.store.put('history',{'id':'BVtest','position':10})
        data=self.store.export_data()
        self.assertNotIn('cookie',data['settings'])
        self.store.remove('history','BVtest');self.store.import_data(data)
        self.assertEqual(self.store.items('history')[0]['position'],10)

    def test_invalid_backup_is_atomic(self):
        self.store.set('theme','light')
        with self.assertRaises(ValueError):self.store.import_data({'format':'gnome-media-profile','version':1,
            'settings':{'theme':'dark'},'library':[['bad']]})
        self.assertEqual(self.store.get('theme'),'light')

    def test_wbi_does_not_mutate_request(self):
        original={'keyword':'中文 & x','page':1}
        value=sign(original,'0123456789abcdef',1234)
        self.assertEqual(value['keyword'],original['keyword'])
        self.assertEqual(value['wts'],1234)
        self.assertNotIn('wts',original)
        self.assertEqual(value,sign({'page':1,'keyword':'中文 & x'},'0123456789abcdef',1234))

    def test_titles_are_plain_text(self):
        item=Service.item({'bvid':'BVtest','title':'<em>搜索</em> &amp; 视频','owner':{'name':'UP'}})
        self.assertEqual(item['title'],'搜索 & 视频')

    def test_dash_retains_audio_and_selected_page(self):
        service=Service(None,self.store)
        service.detail=lambda item:{'cid':100}
        called=[]
        def request(path,params,wbi):
            called.append(params)
            return {'dash':{'video':[{'id':64,'baseUrl':'https://media.example/video','bandwidth':500}],
                            'audio':[{'baseUrl':'https://media.example/audio','bandwidth':128}]}}
        service.request=request
        value=service.play({'id':'BVtest','cid':200,'title':'test','url':'https://bilibili.com/video/BVtest'})
        self.assertEqual(called[0]['cid'],200)
        self.assertEqual(value['audio'],'https://media.example/audio')
        self.assertEqual(value['headers']['Referer'],'https://www.bilibili.com/')

    def test_api_errors_are_not_empty_success(self):
        class Http:
            def json(self,*args,**kwargs):return {'code':-101,'message':'账号未登录'}
        with self.assertRaisesRegex(ValueError,'-101'):
            Service(Http(),self.store).request('/x/example')


if __name__=='__main__':unittest.main()
