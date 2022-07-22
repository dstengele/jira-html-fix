# HTML Migrator Script for Jira
This script can be used to migrate Jira projects from JEditor back to the
default Editor. As JEditor uses HTML as storage format, this calls pandoc to
convert to Jira markup.

To make sure that Jira does not send e-Mails for every edited issue and comment,
the script switches the notification scheme beforehand to the one defined in the
config. This has to be empty to ensure no notifications during the run. Afterwards
or if the script is interrupted, the scheme is reset to the old one again.

## Dependencies
* [Pandoc](https://pandoc.org/)

## Usage
Rename `config.sample.json` to `config.json` and fill in the required config. Then simply run `main.py`.
