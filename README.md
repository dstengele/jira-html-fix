# HTML Migrator Script for Jira
This script can be used to migrate Jira projects from JEditor back to the
default Editor. As JEditor uses HTML as storage format, this calls pandoc to
convert to Jira markup.

To make sure that Jira does not send e-Mails for every edited issue and comment,
the script disables the notification scheme beforehand. If the script is
interrupted, this won't be reset, but the old notification scheme is logged to
comment-fix.log at the bgeinning of the run so you will have to set it manually.

## Dependencies
* [Pandoc](https://pandoc.org/)

## Usage
Set the project(s) that are to be migrated at the end of the script, make sure
you are logged in to Jira in a browser and run the script.
