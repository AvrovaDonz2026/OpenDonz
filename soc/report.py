#!/usr/bin/env python3
"""Recreate resource evidence and arithmetic capacity screen, not a floorplan."""
import pathlib, json, re, hashlib, shutil, yaml
r=pathlib.Path(__file__).resolve().parent.parent
s=r/'soc'; ev=s/'evidence'; ev.mkdir(exist_ok=True)
areas={}
for name in ['ibex','usbdev','debug','dtm','rom','boundary']:
 t=(s/f'build/{name}-gf180.log').read_text()
 areas[name]=float(re.findall(r"Chip area for module .*?: ([0-9.]+)",t)[-1])
 (ev/(name+'-mapping-summary.txt')).write_text('\n'.join(line.rstrip() for line in t.splitlines()[-90:]).rstrip()+'\n')
 shutil.copyfile(s/f'build/{name}-inputs.json',ev/(name+'-inputs.json'))
lef=ev/'sram1024x8.lef';w,h=map(float,re.search(r'SIZE ([0-9.]+) BY ([0-9.]+)',lef.read_text()).groups());macro=w*h
slots={}
for f in (r/'librelane/slots').glob('*.yaml'):
 a=yaml.safe_load(f.read_text())['CORE_AREA']; slots[f.stem]=dict(core_um2=(a[2]-a[0])*(a[3]-a[1]),bounds=a)
logic=areas['ibex']+42090.7648+areas['debug']+areas['dtm']+areas['rom']
scenarios=[]
for ram in [8,16]:
 for usb in ['light','full']:
  cells=logic if usb=='light' else logic-42090.7648+areas['usbdev']
  scenarios.append(dict(ram_kib=ram,usb=usb,macro_um2=macro*ram,cell_um2=cells,occupied_um2=macro*ram+cells,planning_core_um2_at_50pct_cells_10pct_macro=macro*ram*1.1+cells/0.5,unmeasured='bus, EP0/HID buffer and controller, timer, GPIO, RNG, NVM/QSPI, clocks, pad/PHY, power network'))
(ev/'capacity.json').write_text(json.dumps(dict(areas_um2=areas,sram=dict(width_um=w,height_um=h,area_um2=macro,source_commit='d41c7447d34d0c298158094378c8268560941724',sha256=hashlib.sha256(lef.read_bytes()).hexdigest()),slots=slots,scenarios=scenarios,note='Arithmetic capacity screen, NOT placement, timing, DRC or signoff; excludes new USB bridge and OTBN/HMAC; generic usbdev SRAM-to-flop area does not disqualify macro-adapted OpenTitan',crypto_priority='OpenTitan OTBN P256 + OT HMAC preferred; measured image is Mbed TLS reference/development backend only',software_reference_static_ram_bytes=9760),indent=2)+'\n')
fe=r/'firmware/evidence';fe.mkdir(exist_ok=True)
for f in ['size.txt','elf.txt','inputs.json','stack.json','execution.json','crypto-edge.json']:
 shutil.copyfile(r/'firmware/build'/f,fe/f)
shutil.copyfile(s/'evidence/capacity.json',fe/'capacity.json')
print('Resource evidence refreshed; no physical signoff claimed.')
