import concurrent
from concurrent.futures import ThreadPoolExecutor

from jira import JIRA, JIRAError
import pypandoc
import json
import logging
import requests
import threading


class JiraCommentFixer(object):
    def __init__(self, config):
        self.base_url = config['base_url']
        self.auth = (config['username'], config['password'])

        self.customfields = config.get('customfields', [])
        self.projects = config['projects']
        self.additional_jql = config.get('additional_jql', '')

        self.disabled_notification_scheme = config['disabled_notification_scheme']

        self.jira = JIRA(
            self.base_url,
            basic_auth=self.auth
        )

        self.issues_with_errors = set()
        self.issues_with_errors_lock = threading.Lock()

    def run(self):
        for project in self.projects:
            self.work_on_project(project)

        if self.issues_with_errors:
            print(f'The following issues could not be updated: {", ".join(self.issues_with_errors)}')

    def disable_notifications(self, project):
        project_json = requests.get(
            f"{self.base_url}/rest/api/latest/project/{project}/notificationscheme",
            auth=self.auth
        ).json()
        notification_scheme_id = project_json.get("id", None)
        notification_scheme_name = project_json.get("name", None)

        logging.info(
            f"Current notification scheme for project {project}: {notification_scheme_name} ({notification_scheme_id})"
        )

        requests.put(
            f"{self.base_url}/rest/api/latest/project/{project}",
            auth=self.auth,
            json={"notificationScheme": self.disabled_notification_scheme},
        )

        return notification_scheme_id

    def enable_notifications(self, project, notification_scheme_id):
        requests.put(
            f"{self.base_url}/rest/api/latest/project/{project}",
            auth=self.auth,
            json={"notificationScheme": notification_scheme_id},
        )

    def work_on_project(self, project):
        self.issues_with_errors = set()
        current_notification_scheme = self.disable_notifications(project)

        try:
            jql = f'issueFunction in htmlIssues("{project}") {f"AND {self.additional_jql}" if self.additional_jql else ""} order by issuekey desc'

            with ThreadPoolExecutor(max_workers=40) as ex:
                wait_for = []
                error_keys_jql = ""

                idx = 0
                while issues := self.jira.search_issues(error_keys_jql + jql, maxResults=100, startAt=0):
                    logging.info(f"Got {len(issues)} new issues.")
                    for issue in issues:
                        wait_for.append(ex.submit(self.work_on_issue, issue))

                    if len(issues) < 100:
                        break

                    idx += 100

                    error_keys_jql = f'issuekey not in ({", ".join(self.issues_with_errors)}) and ' if self.issues_with_errors else ""

                concurrent.futures.wait(wait_for)

                for fut in wait_for:
                    if exp := fut.exception():
                        logging.exception(exp)
        except KeyboardInterrupt:
            logging.info("Run cancelled, restoring notification scheme...")
        finally:
            self.enable_notifications(project, current_notification_scheme)

    def work_on_issue(self, issue):
        try:
            fields_to_update = self.customfields + ["description"]

            update_dict = {}
            for field in fields_to_update:
                old_value = getattr(issue.fields, field, None)
                if old_value and old_value.startswith("<"):
                    logging.info(f"Updating {field} for issue {issue.key}")
                    update_dict[field] = pypandoc.convert_text(old_value, "jira", "html")

            try:
                if update_dict:
                    issue.update(notify=False, fields=update_dict)
            except JIRAError as e:
                logging.warning(f"Issue {issue.key} could not be updated: {e}")
                with self.issues_with_errors_lock:
                    self.issues_with_errors.add(issue.key)

            for comment in self.jira.comments(issue):
                if not comment.body.startswith("<"):
                    continue
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
        except Exception as e:
            logging.exception(e)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
        filename="comment-fix.log",
        filemode="a+",
    )

    with open('config.json', 'r') as configfile:
        config = json.load(configfile)

    runner = JiraCommentFixer(config)

    runner.run()