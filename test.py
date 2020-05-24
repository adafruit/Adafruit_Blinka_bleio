import _bleio
import time

ses = []
a = _bleio.adapter
start_time = time.time()
for se in a.start_scan(timeout=5.0):
    if isinstance(se, int):
        print(se)
    else:
        print(f"{se = !s}, {se.rssi = }")
    ses.append(se)
    # Test stopping early
    if len(ses) >= 2:
        break

a.stop_scan()
