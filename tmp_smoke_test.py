import urllib.request, time
urls=['http://127.0.0.1:8000/','http://127.0.0.1:8000/user-manual/']
for url in urls:
    ok=False
    for i in range(10):
        try:
            r=urllib.request.urlopen(url, timeout=2)
            print(url, '->', r.getcode())
            ok=True
            break
        except Exception as e:
            time.sleep(0.4)
    if not ok:
        print(url, '-> failed')
