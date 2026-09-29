#!/usr/bin/env python3
"""Summarize UI38/UI39 times from an idevicesyslog capture. No network access."""
import argparse,re
from pathlib import Path

ap=argparse.ArgumentParser()
ap.add_argument('log',type=Path)
a=ap.parse_args()
if not a.log.is_file():raise SystemExit('Missing log: '+str(a.log))
rows={}
for line in a.log.read_text(errors='replace').splitlines():
 m=re.search(r'Blender3GS\[(\d+)\].*?Blender3GS (.*)',line)
 if not m:continue
 pid,body=m.groups(); d=rows.setdefault(pid,{'stages':0,'errors':0})
 for key,patt in [('homefile_ms',r'UI28 STARTUP: homefile_complete=([\d.]+)'),
                  ('python_ms',r'UI31 PY: complete elapsed_ms=([\d.]+)'),
                  ('bpy_ms',r'UI32 BPY: bpy_import_done elapsed_ms=([\d.]+)'),
                  ('wm_ms',r'UI30 INIT: wm_init_complete elapsed_ms=([\d.]+)'),
                  ('draw_ms',r'UI28 FRAME: index=1 .*?total=([\d.]+)'),
                  ('panels',r'UI17 PROPERTIES: .*?panels=(\d+)')]:
  n=re.search(patt,body)
  if n:d[key]=float(n.group(1))
 if 'UI37 STAGE: batch=' in body:
  d['stages']+=1
  if 'rc=-1' in body:d['errors']+=1
 if 'LIFE: background' in body:d['background']=True
for pid,d in rows.items():
 if 'wm_ms' not in d:continue
 total=d['wm_ms']+d.get('draw_ms',0)
 print('PID',pid,'homefile_ms=',d.get('homefile_ms','?'),
       'python_ms=',d.get('python_ms','?'),'bpy_ms=',d.get('bpy_ms','?'),
       'first_frame_estimated_from_INIT_ms=',round(total,1),
       'panels_last_seen=',int(d['panels']) if 'panels' in d else '?',
       'stage_logs=',d['stages'],'stage_errors=',d['errors'],
       'background=',d.get('background',False))
print('NOTE: first_frame_estimated_from_INIT_ms excludes time before UI30 INIT begin.')
