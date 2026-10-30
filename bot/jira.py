"""Creación de tareas en Jira Cloud (REST v2, descripción en wiki markup)."""
import base64
import json
import urllib.error
import urllib.request
from datetime import date

from . import net


class JiraError(RuntimeError):
    pass


class Jira:
    def __init__(self, base_url: str, email: str, token: str, project_key: str, issue_type: str):
        self._base = base_url
        self._project = project_key
        self._issue_type = issue_type
        cred = base64.b64encode(f"{email}:{token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {cred}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def browse_url(self, key: str) -> str:
        return f"{self._base}/browse/{key}"

    def create_task(self, summary: str, description: str, due: date,
                    assignee_id: str, labels: list[str]) -> str:
        fields = {
            "project": {"key": self._project},
            "issuetype": {"name": self._issue_type},
            "summary": summary[:250],
            "description": description,
            "duedate": due.isoformat(),
            "labels": labels,
        }
        if assignee_id:
            fields["assignee"] = {"accountId": assignee_id}
        req = urllib.request.Request(
            f"{self._base}/rest/api/2/issue",
            data=json.dumps({"fields": fields}).encode(),
            headers=self._headers,
            method="POST",
        )
        try:
            with net.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())["key"]
        except urllib.error.HTTPError as err:
            raise JiraError(f"Jira {err.code}: {err.read().decode()[:500]}") from err
