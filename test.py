import _bleio

ses = []
a = _bleio.adapter
for se in a.start_scan(timeout=2.0):
    print(f"{se = !s}, {se.rssi = }")
    ses.append(se)
    if se == 1:
        a.stop_scan()
