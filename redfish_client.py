import requests
from types import SimpleNamespace

class RedfishClient:
    """Minimal Redfish client using HTTP basic auth."""

    def __init__(self, base_url: str, username: str, password: str, default_prefix: str = "/redfish/v1"):
        self.base_url = base_url.rstrip('/')
        self.prefix = default_prefix.rstrip('/')
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.verify = False  # self-signed certs common on iDRAC
        requests.packages.urllib3.disable_warnings()

    def login(self):
        """Placeholder for compatibility."""
        pass

    def logout(self):
        self.session.close()

    def get(self, path: str):
        url = path if path.startswith('http') else f"{self.base_url}{path}"
        resp = self.session.get(url)
        resp.raise_for_status()
        return SimpleNamespace(dict=resp.json(), headers=resp.headers)

    def simple_update(self, image_uri: str):
        url = f"{self.base_url}{self.prefix}/UpdateService/Actions/UpdateService.SimpleUpdate"
        resp = self.session.post(url, json={"ImageURI": image_uri})
        resp.raise_for_status()
        return SimpleNamespace(headers=resp.headers)
