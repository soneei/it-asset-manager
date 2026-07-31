import sys
import urllib.request
import json
import os

BASE_URL = "http://localhost:8081"

def test_api():
    try:
        # Check export endpoint
        print("Testing /api/export_excel...")
        req = urllib.request.Request(f"{BASE_URL}/api/export_excel")
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print("Export endpoint OK.")
                with open("test_export.xlsx", "wb") as f:
                    f.write(response.read())
                print("Downloaded test_export.xlsx")
            else:
                print(f"Export endpoint returned status code: {response.status}")

    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    test_api()
