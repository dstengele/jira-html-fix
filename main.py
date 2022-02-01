import concurrent
from concurrent.futures import ThreadPoolExecutor

from jira import JIRA, JIRAError
import pypandoc
import logging
import requests
import browser_cookie3


class JiraCommentFixer(object):
    def __init__(self, domain, context_path, projects, additional_jql=None):
        self.base_url = f"https://{domain}{context_path}"
        self.cookies = browser_cookie3.load(domain_name=domain)

        self.jira = JIRA(
            self.base_url,
            options={"cookies": self.cookies},
        )

        self.projects = projects

        self.additional_jql = additional_jql

    def run(self):
        for project in self.projects:
            self.work_on_project(project)

    def disable_notifications(self, project):
        project_json = requests.get(
            f"{self.base_url}/rest/api/latest/project/{project}/notificationscheme",
            cookies=self.cookies,
        ).json()
        notification_scheme_id = project_json.get("id", None)
        notification_scheme_name = project_json.get("name", None)

        logging.info(
            f"Current notification scheme for project {project}: {notification_scheme_name} ({notification_scheme_id})"
        )

        requests.put(
            f"{self.base_url}/rest/api/latest/project/{project}",
            cookies=self.cookies,
            json={"notificationScheme": 13400},
        )

        return notification_scheme_id

    def enable_notifications(self, project, notification_scheme_id):
        requests.put(
            f"{self.base_url}/rest/api/latest/project/{project}",
            cookies=self.cookies,
            json={"notificationScheme": notification_scheme_id},
        )

    def work_on_project(self, project):
        current_notification_scheme = self.disable_notifications(project)

        issues = self.jira.search_issues(
            f'project = "{project}" {f"AND {self.additional_jql}" if self.additional_jql else ""} order by project',
            maxResults=False,
        )
        logging.info(f"Issues: {issues}")
        with ThreadPoolExecutor(max_workers=20) as ex:
            wait_for = []
            for issue in issues:
                wait_for.append(ex.submit(self.work_on_issue, issue))
            concurrent.futures.wait(wait_for)

        self.enable_notifications(project, current_notification_scheme)

    def work_on_issue(self, issue):
        logging.info(f"Checking issue {issue.key}")
        fields_to_update = [
            "customfield_10406",
            "customfield_10413",
            "customfield_10426",
            "customfield_11500",
            "customfield_13100",
            "customfield_13202",
            "customfield_13900",
            "customfield_16000",
            "customfield_18117",
            "customfield_18908",
            "customfield_20606",
            "customfield_20610",
            "customfield_21505",
            "description",
        ]

        update_dict = {}
        for field in fields_to_update:
            old_value = getattr(issue.fields, field, None)
            if old_value and old_value.startswith("<"):
                logging.info(f"Updating {field} for issue {issue.key}")
                update_dict[field] = pypandoc.convert_text(old_value, "jira", "html")

        try:
            issue.update(notify=False, fields=update_dict)
        except JIRAError:
            logging.warning(f"Issue {issue.key} could not be updated.")
        for comment in self.jira.comments(issue):
            if comment.body.startswith("<"):
                logging.info(f"Updating comment {comment.id} for issue {issue.key}")
                markup_comment_body = pypandoc.convert_text(
                    comment.body, "jira", "html"
                )
                try:
                    comment.update(body=markup_comment_body)
                    pass
                except JIRAError:
                    logging.warning(
                        f"Comment {comment.id} in issue {issue.key} could not be updated."
                    )


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
        filename="comment-fix.log",
        filemode="a+",
    )

    runner = JiraCommentFixer(
        domain="jira.example.com",
        context_path="/",
        projects=["EXAMPLE"],
        additional_jql="",
    )

    runner.run()
