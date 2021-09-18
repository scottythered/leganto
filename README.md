# Leganto Automation
The main purpose of this repository is automating the process of loading course and instructor data into Alma so that it can be used by Alma's Leganto Reading Lists application.

This system requires the Alma integration profile to be configured correctly as well as authentication with the SFTP server to receive files from UTO (with the CEM data) and to send files to ExL.

## Overall Process
The process is set up to run every morning around 9:20 am, AZ time:
1. Grab CEM data file received from TOPS/UTO (on libfile SFTP)
2. Reformat CEM data to Alma format
3. Add the processing department based on some logic
4. Rename file with datestamp and push to sftp directory
5. Alma job will then pick it up and process on schedule
6. Once Alma is finished processing, the Rollover Report script runs
7. When the Rollover Report is done, the report is emailed and a Slack notification is sent

The Alma file must be `[datestamp].csv` or `[datestamp].txt` with tab-separation, in UTF-8 or ASCII with CRLF line termination. The first row must be a header row.

Alma documentation: https://knowledge.exlibrisgroup.com/Leganto/Product_Documentation/Leganto_Administration_Guide/Configuring_Leganto_Integration_Profiles/Configuring_Course_Loading

2021 UPDATE: the Leganto code was updated in early 2021, adding asynchronous HTTP call functionality, which cut the 5-6 hour runtime in half. (Note: because the code relies on Alma picking up the file and processing it, it still takes a significant time for Alma to process. )


## Main Files
1. `leganto_run.sh` - this file is initiated via a cron task like crontab `47 7 * * * /Users/ezoller/Sites/leganto/leganto_run.sh` - it is what calls the python script to kick off this work. (Note that because this file contains an API key, this is not included in the repo. See Scott or Eli to access.)
2. `leganto.py` - this is the main python script initiated by the above shell script. It basically performs calls out to the separate python scripts and passes the files between those steps of work.
3. `leganto_pull.py` - pulls the CEM data from the SFTP server, which UTO puts there.
4. `leganto_transform.py` - transforms the CEM data into a file that is readable by Alma. Also applies custom logic to manipulate or add to the data as necessary.
5. `leganto_push.py` - pushes the output file from the transform process onto the SFTP where Alma can pick it up daily to run the course load job. The frequency of that job run is configured in Alma.
6. `leganto_rollover.py` - this generates and emails a report of potential rollovers based on the "rollover" functionality which instructors can request directly in CEM. Since we cannot rely on the "rollover" mechanism in the CEM being used the same way we would consider a rollover happening in Alma, we have decided not to have this happen automatically but instead to generate a report for humans to review.
7. `leganto_shared.py` - NEW! a catch-all library for functions used by multiple Leganto scripts/processes.
8. `leganto_logger.py` - NEW! this governs logging data, so that each daily shell script run has its own separate log.
9. `course_caching.py` - NEW! this adds asynchronous HTTP call functionality to the Leganto process.


## Supplementary Files
1. `leganto_files_cleanup.py` - NEW! the Leganto process generates a LOT of files. Run this once every few months to clean things up -- it will keep the most recent 6 weeks' worth of files. Run it from the Leganto home directory with `python3.8 leganto_files_cleanup.py`
2. `leganto_delete_empty_courses.py` - used to delete courses from our Leganto instance. May be superfluous due to ExL giving the user interface greater control over course deletion.
3. `leganto_rollovers_only.py` - in the (increasingly likely) event of an issue with TOPS delivering the data, the SFTP of the data to our Libfile server, or anything unforeseen event that kills the Leganto process and knocks it off its regular timeslot, this standalone script can be run after Alma picks up the CEM file.


## Deprecated Files
1. `leganto_course_report.py` - this report queried the API for courses and looked at the courses created in the last day, then it checks to see if those new courses match any existing courses (with reading lists) that have the same course code and instructor. it emails those results. **Removed from production at the request of Bob Marley on  6/1/2021.**
2. `leganto_only_reports.py` - this script was used if timed-out API connection killed the original Leganto process during the Rollover report phase -- no longer used due to deprecation of (1) above. Replaced by `leganto_rollovers_only.py`.


## Deploying
You can deploy this to the lsp-sync-dev or lsp-sync servers with the provided ansible deploy script:
```
ansible-playbook deploy.yml --vault-id leganto_pass@/home/scottythered/.leganto_pass
```

It requires an ansible vault key located at `.leganto_pass`.

You can view/decrypt with ansible-vault with commands like
```
ansible-vault edit password.yml --vault-id leganto_pass@/home/scottythered/.leganto_pass --vault-password-file=/Users/ezoller/.leganto_pass
```
where you specify the path to that password file

If you're dev-ing locally you'll need to save the passwords as local files, like the ansible script does.


## Data Required from UTO
UTO owns the CEM data needed for this integration; TOPS (Technical Operations Production Support) runs the query and all changes. The output file from UTO currently comes from the tables `Cem_Course_Xwalk_To_Sln`, `Cem_Courses`, `Cem_Instructors` and includes the following fields: `course ID`, `SLN`, `name`, `status`, `year`, `term`, `college`, `campus`, `copy course info` and for instructors fields like `asurite`, `type of instructor`.


## Query Changes
Each semester, a ticket in Service-now must be submitted to modify the terms in the query that results in the data that UTO places on Libstor from CEM. You can do this by going to Service Now, creating a new Request under Infrastructure > Database > Request Administration. Then you choose Request Type Data Integration (SSIS) and Modify an existing integration. Enter the query terms you'd like to change, such as `Leganto/Alma CEM query should contain Cem_Courses.Asu_Strm IN ('2201', '2204')`


## Password Changes
1. Request a password change at https://asu.service-now.com -- assigned group: Technical Operations Production Support (TOPS).
2. Details > More information: "Control-M job FTPLEGANTO01 that uses connection profile titled "Libstor" password has changed and needs to be updated. Please contact for new password."
3. Click "order now." They will call/contact you in some way. When they do, give them the new leganto-sftp password from LastPass.
4. Use the ansible vault key (located at `.leganto_pass`) with the view/decrypt command while in the Leganto directory:
```
sudo ansible-vault edit /mnt/c/git/leganto/password.yml --vault-id leganto_pass@/home/scottythered/.leganto_pass --vault-password-file=/home/scottythered/.leganto_pass
```
5. Enter the new LSP-Sync SFTP password from LastPass and write/quit using the VI command: `:wq`
6. Update the git repo, then deploy:
```
sudo ansible-playbook /mnt/c/git/leganto/deploy.yml -i /mnt/c/git/leganto/hosts --vault-id leganto_pass@/home/scottythered/.leganto_pass
```
