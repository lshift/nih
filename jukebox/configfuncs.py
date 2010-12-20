from jsonrpc import jsonrpc_method
from models import *
from spider import get_spider
from urllib2 import urlopen, HTTPError

@jsonrpc_method("all_roots")
def all_roots(request):
	ret = []
	for root in WebPath.get_root_nodes():
		ret.append({"url":root.url, "count":MusicFile.objects.filter(url__startswith=root.url).count()})
	return ret

@jsonrpc_method("current_rescans")
def current_rescans(request):
	ret = []
	for root in WebPath.get_root_nodes():
		if WebPath.objects.filter(checked = False).filter(url__startswith=root.url).count()>0:
			ret.append(root.url)
	return ret

@jsonrpc_method("rescan_root")
def rescan_root(request, root):
	for x in WebPath.get_root_nodes():
		if x.url == root:
			MusicFile.objects.filter(url__startswith=root).delete()
			WebPath.objects.filter(url__startswith=root).update(checked = False)
			break
	else:
		try:
			urlopen(root)
		except:
			return # crap url
		WebPath.add_root(url=root)
		
	get_spider()
