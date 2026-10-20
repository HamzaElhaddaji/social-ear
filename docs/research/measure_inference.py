import ctypes,json,time,statistics,sys
from ctypes import wintypes
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
class P(ctypes.Structure):
 _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
def mem():
 p=P(); p.cb=ctypes.sizeof(p)
 ctypes.windll.kernel32.GetCurrentProcess.restype=wintypes.HANDLE
 ctypes.windll.psapi.GetProcessMemoryInfo(wintypes.HANDLE(ctypes.windll.kernel32.GetCurrentProcess()),ctypes.byref(p),p.cb)
 return {'rss_MiB':round(p.WorkingSetSize/2**20,1),'peak_rss_MiB':round(p.PeakWorkingSetSize/2**20,1)}
mode=sys.argv[1]
if mode=='onnx':
 from app.sentiment_model import predict
 f=lambda s:predict(s,'en')
else:
 from app.intelligence import sentiment_score
 f=sentiment_score
s='I cannot log in and support is not responding.'
t=time.perf_counter();f(s);cold=time.perf_counter()-t
for _ in range(2):f(s)
a=[]
for _ in range(30):
 t=time.perf_counter();f(s);a.append((time.perf_counter()-t)*1000)
r={'mode':mode,'n':30,'batch_size':1,'cold_first_call_ms':round(cold*1000,2),'median_ms':round(statistics.median(a),2),'p95_ms':round(sorted(a)[28],2),**mem()}
(Path(__file__).resolve().parent / (mode+'-latest.json')).write_text(json.dumps(r,indent=2));print(json.dumps(r))
