
import requests

DELETE_PLOT_API = "http://example.com/api/delete"

def phase1_send_deletes(headers, delete_api=DELETE_PLOT_API):
    requests.post(delete_api, headers=headers)

# Call it with keyword arg (reproducing the issue)
phase1_send_deletes({}, delete_api=DELETE_PLOT_API)

# Call it without arg (relying on default - also a test case)
phase1_send_deletes({})
