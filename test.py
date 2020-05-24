import _bleio

ses = []
a = _bleio.adapter
for se in a.start_scan(timeout=4.0):
    if isinstance(se, int):
        print(se)
    else:
        print(f"{se = !s}, {se.rssi = }")
    ses.append(se)
    # if se == 2:
    #     a.stop_scan()
