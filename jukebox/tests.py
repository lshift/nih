from django.test import TestCase
from django.test.client import Client
from jsonrpc._json import loads, dumps
from uuid import uuid1
from jukebox.models import *
from time import sleep
import utils
from spider import spider
from downloader import downloader

class JukeboxTest(TestCase):
	static_path = "http://localhost/static/"
	test_track_path = static_path+"silent-3mins.mp3"
	def _configmethod(self, method, *params, **kwargs):
		return self._method(method, path="/rpc/config", *params)

	def _method(self, method, *params, **kwargs):
		req = {
		  u'version': u'1.1',
		  u'method': method,
		  u'params': params,
		  u'id': u'random_test_id'
		}
		return self._call(req, **kwargs)
	
	def _call(self, req, path="/rpc/jukebox"):
		resp = loads(self.client.post(path, dumps(req), content_type="application/json").content)
		self.assert_("result" in resp.keys(), resp)
		return resp["result"]

	def needs_static(self):
		while len(spider.todo())>0:
			print "spider todo", spider.todo()
			sleep(.5)

	def needs_downloaded(self):
		while len(downloader.todo())>0:
			print "downloader todo", downloader.todo()
			sleep(.5)

class MainFunctions(JukeboxTest):
	def setUp(self):
		utils.client = self.client
		self._configmethod("rescan_root", self.static_path)

	def clear_queue(self):
		QueueItem.objects.all().delete() # clear anything else in there

	def _addTestTrack(self, url = None):
		root = WebPath.objects.filter(url = "http://localhost")
		if root.count() == 0:
			root = WebPath()
			root.url = "http://localhost"
			root.save()
		else:
			root = root[0]

		if url == None:
			url = "http://localhost/"+uuid1().hex
		if MusicFile.objects.filter(url = url).count() == 0:
			m = MusicFile()
			m.url = url
			m.parent = root
			m.save()
			print "added test track", url
		else:
			print "test track already present", url
		return url

	def _enqueueTestTrack(self, atTop=False):
		url = self._addTestTrack()
		resp = self._method("enqueue", "test_user", [{"url":url}], atTop)
		return (url, resp)

	def _enqueueRealTrack(self):
		self.needs_static()
		url = self._addTestTrack(self.test_track_path)
		resp = self._method("enqueue", "test_user", [{"url":url}], False)
		return (url, resp)

	def testEnqueue(self):
		downloader.pause()
		(url, res) = self._enqueueTestTrack()
		self.assertEquals(res[u'entry'][u'url'], url)
		self.assertEquals(res[u'entry'][u'username'], "test_user")
		self.assertEquals(res[u'queue'], [])
		(url, res) = self._enqueueTestTrack(True)
		self.assertEquals(len(res[u'queue']), 1)
		downloader.unpause()

	def testPlay(self): 
		self.clear_queue()
		res = self._method("pause", False)
		self.assertEqual(res['status'], "idle", res)
		self.assertEqual(res['entry'], None, res)
		self.assertEqual(res['queue'], [], res)

		self.needs_downloaded()
		sleep(.2) # wait for gstreamer to catch up
		(url, _) = self._enqueueTestTrack()
		res = self._method("pause", False)
		self.assertEqual(res['paused'], False, res)
		self.assertEqual(res['status'], "caching", res)

	def testSkip(self): 
		self.clear_queue()

		(url, _) = self._enqueueRealTrack()
		(url2, _) = self._enqueueRealTrack()

		res = self._method("get_queue")
		self.assertEqual(res['entry']['url'], url, res)
		res = self._method("skip", "test_user")
		self.assertEqual(res['entry']['url'], url2, res)
		res = self._method("skip", "test_user")
		self.assertEqual(res['entry'], None, res)

	def testSkipWithPlay(self): 
		(url, _) = self._enqueueRealTrack()
		(url2, _) = self._enqueueRealTrack()

		self.needs_downloaded()
		res = self._method("pause", False)
		self.assertNotEqual(res['entry'], None, res)
		self.assertEqual(res['entry']['url'], url, res)
		self.assertEqual(res['paused'], False, res)
		self.assertEqual(res['status'], "playing", res)

		res = self._method("skip", "test_user")
		self.assertEqual(res['entry']['url'], url2, res)

		res = self._method("skip", "test_user")
		self.assertEqual(res['entry'], None, res)

	def testPlay(self):
		self.clear_queue()

		res = self._method("pause", False)
		self.assertEqual(res['entry'], None, res)
		(url, _) = self._enqueueRealTrack()
		self.needs_downloaded()
		res = self._method("pause", False)
		self.assertEqual(res['paused'], False, res)
		self.assertEqual(res['status'], "playing", res)

	def testNotCachedYet(self):
		print "starting cache test"
		self.clear_queue()
		downloader.pause()

		(url, _) = self._enqueueTestTrack()
		(url2, _) = self._enqueueTestTrack()

		res = self._method("pause", False)
		self.assertNotEqual(res['entry'], None, res)
		self.assertEqual(res['entry']['url'], url, res)
		res = self._method("skip", "test_user")
		self.assertNotEqual(res['entry'], None, res)
		self.assertEqual(res['entry']['url'], url2, res)
		res = self._method("skip", "test_user")
		self.assertEqual(res['entry'], None, res)

		downloader.unpause()

	def testGetHostname(self):
		res = self._method("get_caller_hostname")
		self.assertEqual(res, "127.0.0.1")

	def testRandom(self):
		self.needs_static()
		res = self._method("randomtracks", 1)
		self.assertEqual(len(res), 1)
		self.assertEqual(res[0]["url"], self.test_track_path)

class ConfigTests(JukeboxTest):
	def testAllRoots(self):
		self._configmethod("rescan_root", self.static_path)
		self.needs_static()
		roots = self._configmethod("all_roots")
		self.assertEqual(len(roots), 1)
		self.assertEqual(roots[0]["url"], self.static_path)
		self.assertEqual(roots[0]["count"], 1)

	def testCurrentRescans(self):
		spider.pause()
		self._configmethod("rescan_root", self.static_path)
		rescans = self._configmethod("current_rescans")
		self.assertEqual(len(rescans), 1)
		self.assertEqual(rescans[0], self.static_path)
		spider.unpause()

	def testRescanRoot(self):
		self._configmethod("rescan_root", self.static_path)
		self._configmethod("rescan_root", self.static_path)

	def testBadScanTarget(self):
		self._configmethod("rescan_root", "foo")

	def testRemoveRoot(self):
		self._configmethod("rescan_root", self.static_path)
		rootcount = len(self._configmethod("all_roots"))
		self.assertEqual(len(self._configmethod("remove_root", self.static_path)), rootcount - 1)

