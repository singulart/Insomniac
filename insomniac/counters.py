
def to_int(counter):
    if 'K' in counter:
        if ',' in counter or '.' in counter:
            return int(counter[: -1].replace(',', '').replace('.', '')) * 100
        else:
            return int(counter[: -1]) * 1000
    if 'M' in counter:
        if ',' in counter or '.' in counter:
            return int(counter[: -1].replace(',', '').replace('.', '')) * 100000
        else:
            return int(counter[: -1]) * 1000000
    if ',' in counter or '.' in counter:
        return int(counter.replace(',', '').replace('.', ''))
    else:
        return int(counter)
