#!/usr/bin/env python3
"""Fetch exact source revisions; retain complete upstream licenses and notices."""
import pathlib, subprocess, tarfile, tempfile, urllib.request
r=pathlib.Path(__file__).resolve().parent
for repo,rev in [('gl-sergei/u2f-token','2c19a75c31096e19cbcfcedeae6bb18077eabac0'),('kmackay/micro-ecc','541b3a78026420a3e369c4c9281c396b5e531113'),('Mbed-TLS/mbedtls','e185d7fd85499c8ce5ca2a54f5cf8fe7dbe3f8df')]:
 name=repo.split('/')[1]+'-'+rev
 if (r/'vendor'/name).exists():continue
 (r/'vendor').mkdir(exist_ok=True)
 with tempfile.TemporaryDirectory() as t:
  archive=pathlib.Path(t)/'source.tar.gz'
  urllib.request.urlretrieve('https://codeload.github.com/'+repo+'/tar.gz/'+rev,archive)
  with tarfile.open(archive) as tf:tf.extractall(r/'vendor',filter='data')
print('Pinned sources available. Install test dependencies from requirements-test.txt separately.')
