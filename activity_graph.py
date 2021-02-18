from insomniac.database_engine import get_database, get_sessions
import matplotlib.pyplot as plt
import numpy as np
import sys
from datetime import datetime
from collections import defaultdict

date_format_db = '%Y-%m-%d %H:%M:%S.%f'


username = sys.argv[1]

database = get_database(username)
sessions = get_sessions(database)
buckets = defaultdict(lambda: defaultdict(int))  # funky eh?

for s in sessions:
    date = datetime.strptime(s['start_time'], date_format_db)
    date = date.strftime('%b %d')
    buckets[date]['successful_interactions'] += s['successful_interactions']
    buckets[date]['total_followed'] += s['total_followed']
    buckets[date]['total_likes'] += s['total_likes']
    buckets[date]['total_unfollowed'] += s['total_unfollowed']
    buckets[date]['total_get_profile'] += s['total_get_profile']

X = np.arange(len(buckets) * 2, step=2)
data = [
    [s['successful_interactions'] for s in buckets.values()],
    [s['total_followed'] for s in buckets.values()],
    [s['total_likes'] for s in buckets.values()],
    [s['total_unfollowed'] for s in buckets.values()],
    [s['total_get_profile'] for s in buckets.values()],
]
dates = list(buckets.keys())
plt.figure(figsize=(20, 9))
plt.bar(X - 0.4, data[0], color='b', align='center', width=0.2, label='successful_interactions')
plt.bar(X - 0.2, data[1], color='g', align='center', width=0.2, label='total_followed')
plt.bar(X + 0.0, data[2], color='r', align='center', width=0.2, label='total_likes')
plt.bar(X + 0.2, data[3], color='tab:pink', align='center', width=0.2, label='total_unfollowed')
plt.bar(X + 0.4, data[4], color='tab:cyan', align='center', width=0.2, label='total_get_profile')
font = {'family': 'monospace',
        'weight': 'normal',
        'size': 8}
plt.xticks(np.arange(len(dates) * 2, step=2), dates, rotation=90, **font)
plt.yticks(np.arange(1200, step=100))
plt.legend()
plt.grid()
plt.show()
