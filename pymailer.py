#!/usr/bin/env python3

import csv
import logging
import os
import re
import smtplib
import sys
import string
import ssl
import email

from datetime import datetime
from email.mime.text import MIMEText
from time import sleep

import config # Our file config.py
import argparse

# setup logging to specified log file
logging.basicConfig(filename=config.LOG_FILENAME, level=logging.DEBUG)

class PyMailer():
    """
    A python bulk mailer commandline utility. Takes six arguments: the path to the html file to be parsed; the database of recipients (.csv); the subject of the email; email address the mail comes from; the name the email is from; the number of emails to send to each recipient.
    """
    def __init__(self, html_path, csv_path, subject, *args, **kwargs):
        self.html_path               = html_path
        self.csv_path                = csv_path
        self.subject                 = subject
        self.from_name               = kwargs.get('from_name', config.FROM_NAME)
        self.from_email              = kwargs.get('to_name', config.FROM_EMAIL)
        self.nb_emails_per_recipient = kwargs.get('nb_emails_per_recipient', config.NB_EMAILS_PER_RECIPIENT)
        self.html_template           = None
        self.sslcontext              = None

    def _stats(self, message):
        """
        Update stats log with: last recipient (in case the server crashes); datetime started; datetime ended; total number of recipients attempted; number of failed recipients; and database used.
        """
        try:
            stats_file = open(config.STATS_FILE, 'r')
        except IOError:
            raise IOError("Invalid or missing stats file path.")

        stats_entries = stats_file.read().split('\n')

        # check if the stats entry exists if it does overwrite it with the new message
        is_existing_entry = False
        if stats_entries:
            for i, entry in enumerate(stats_entries):
                if entry:
                    if message[:5] == entry[:5]:
                        stats_entries[i] = message
                        is_existing_entry = True

        # if the entry does not exist append it to the file
        if not is_existing_entry:
            stats_entries.append(message)

        stats_file = open(config.STATS_FILE, 'w')
        for entry in stats_entries:
            if entry:
                stats_file.write("%s\n" % entry)
        stats_file.close()

    def _validate_email(self, email_address):
        """
        Validate the supplied email address.
        """
        if not email_address or len(email_address) < 5:
            return None
        if not re.match(r"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", email_address):
            return None
        return email_address

    def _retry_handler(self, recipient_data):
        """
        Write failed recipient_data to csv file to be retried again later.
        """
        with open(config.CSV_RETRY_FILENAME, 'w+', encoding='utf-8', newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow([
                recipient_data.get('name'),
                recipient_data.get('email')
            ])

    def _html_parser(self, recipient_data):
        """
        Open, parse and substitute placeholders with recipient data.
        """
        
        if not self.html_template:
            with open(self.html_path, 'rt', encoding='utf-8') as html_file:
                html_content = html_file.read()
                if not html_content:
                    raise Exception("The html file is empty.")
                else:
                    self.html_template = string.Template(html_content)

        # replace all placeolders associated to recipient_data keys
        if recipient_data:
            return self.html_template.substitute(recipient_data)
        
        return self.html_template.template

    def _form_email(self, recipient_data):
        """
        Form the html email, including mimetype and headers.
        """
        # get the html content
        html_content = self._html_parser(recipient_data)

        # instatiate the email object and assign headers
        email_message = MIMEText(html_content, 'html')
        email_message['From'] = recipient_data.get('sender')
        email_message['To'] = recipient_data.get('recipient')
        email_message['Subject'] = self.subject
        
        return email_message.as_string()

    def _parse_csv(self, csv_path=None):
        """
        Parse the entire csv file and return a list of dicts.
        """
        is_resend = csv_path is not None
        if not csv_path:
            csv_path = self.csv_path

        with open(csv_path, 'r+t', encoding='utf-8') as csv_file:
            csv_reader = csv.reader(csv_file)

            """
            Invalid emails ignored
            """
            variables_names = []
            recipients_list = []
            for i, row in enumerate(csv_reader):
                # Get header keys
                if i == 0:
                    for cell in row:
                        variables_names.append(cell)
                    continue

                # Get all variables
                variables = {}
                for j, var_name in enumerate(variables_names):
                    if var_name == 'email':
                        if self._validate_email(row[j]):
                            variables[var_name] = row[j]
                            recipients_list.append(variables)
                        else:
                            logging.warning('invalid rceiver address <%s> ignored', row[j])
                    else:
                        variables[var_name] = row[j]

            # clear the contents of the resend csv file
            if is_resend:
                csv_file.write('')

        return recipients_list

    def send(self, retry_count=0, recipient_list=None):
        """
        Iterate over the recipient list and send the specified email.
        """
        if config.ENCRYPT_MODE != 'none' and config.ENCRYPT_MODE != 'ssl' and config.ENCRYPT_MODE != 'starttls':
            raise Exception("Please choose a correct ENCRYPT_MODE")

        if not recipient_list:
            recipient_list = self._parse_csv()
            if retry_count:
                recipient_list = self._parse_csv(config.CSV_RETRY_FILENAME)

        # save the number of recipient and time started to the stats file
        if not retry_count:
            self._stats("TOTAL RECIPIENTS: %s" % len(recipient_list))
            self._stats("START TIME: %s" % datetime.now())

        # instantiate the number of falied recipients
        failed_recipients = 0

        for recipient_data in recipient_list:
            if recipient_data.get('name'):
                recipient_data['recipient'] = "%s <%s>" % (recipient_data.get('name'), recipient_data.get('email'))
            else:
                recipient_data['recipient'] = recipient_data.get('email')

            recipient_data['sender'] = "%s <%s>" % (self.from_name, self.from_email)

            # instantiate the required vars to send email
            message = self._form_email(recipient_data)

            for nb in range(0, self.nb_emails_per_recipient):
                print("Sending to %s..." % recipient_data.get('recipient'))

                if config.ENCRYPT_MODE != 'none' and not self.sslcontext:
                    self.sslcontext = ssl.create_default_context()
                
                if config.ENCRYPT_MODE == 'ssl':
                    smtp_server = smtplib.SMTP_SSL(host=config.SMTP_HOST, port=config.SMTP_PORT, timeout=10, context=self.sslcontext)
                else:
                    smtp_server = smtplib.SMTP(host=config.SMTP_HOST, port=config.SMTP_PORT, timeout=10)

                try:
                    # send the actual email
                    if config.ENCRYPT_MODE != 'none':
                        smtp_server.ehlo()
                        if config.ENCRYPT_MODE == 'starttls':
                            smtp_server.starttls(context=self.sslcontext)
                            smtp_server.ehlo()

                    if config.SMTP_USER and config.SMTP_PASSWORD:
                        smtp_server.login(config.SMTP_USER, config.SMTP_PASSWORD)

                    smtp_server.sendmail(recipient_data.get('sender'), recipient_data.get('recipient'), message)
                    # save the last recipient to the stats file incase the process fails
                    self._stats("LAST RECIPIENT: %s" % recipient_data.get('recipient'))

                    # allow the system to sleep for .25 secs to take load off the SMTP server
                except smtplib.SMTPException as e:
                    print("EXCEPTION")
                    print(repr(e))
                    logging.error("Recipient email address failed: %s\n=== Exception ===\n%s" % (recipient, repr(e)))
                    self._retry_handler(recipient_data)

                    # save the number of failed recipients to the stats file
                    failed_recipients = failed_recipients + 1
                    self._stats("FAILED RECIPIENTS: %s" % failed_recipients)
                finally:
                    smtp_server.quit()
                sleep(config.SLEEP_TIME)

    def send_test(self):
        self.send(recipient_list=config.TEST_RECIPIENTS)

    def resend_failed(self):
        """
        Try and resend to failed recipients two more times.
        """
        for i in range(1, 3):
            self.send(retry_count=i)

    def count_recipients(self, csv_path=None):
        return len(self._parse_csv(csv_path))


def main(sys_args):
    open(config.CSV_RETRY_FILENAME, 'w').close() # Creates a new one or overwrite the old one

    if not os.path.exists(config.STATS_FILE):
        open(config.STATS_FILE, 'w').close()
        
    argparser = argparse.ArgumentParser(prog='pymailer')
    argparser.add_argument("html_path", help="HTML template path")
    argparser.add_argument("csv_path", help="csv path")
    argparser.add_argument("subject", help="subject")
    
    actiongroup = argparser.add_mutually_exclusive_group(required=True)
    actiongroup.add_argument("-t", "--test", help="send test mail to receiver in config file", action="store_true")
    actiongroup.add_argument("-s", "--send", help="send mail to receivers in csv file", action="store_true")
    
    args = argparser.parse_args()

    if not os.path.exists(args.html_path):
        print("The html_path argument doesn't seem to contain a valid html file.")
        sys.exit()

    if not os.path.exists(args.csv_path):
        print("The csv_path argument doesn't seem to contain a valid csv file.")
        sys.exit()

    pymailer = PyMailer(args.html_path, args.csv_path, args.subject)
    
    if args.send:
        if input("You are about to send to %s recipients. Do you want to continue (yes/no)? " % pymailer.count_recipients()) == 'yes':
            # save the csv file used to the stats file
            pymailer._stats("CSV USED: %s" % csv_path)

            # send the email and try resend to failed recipients
            pymailer.send()
            pymailer.resend_failed()
        else:
            print("Aborted.")
            sys.exit()

    elif args.test:
        if input("You are about to send a test mail to all recipients as specified in config.py. Do you want to continue (yes/no)? ") == 'yes':
            pymailer.send_test()
        else:
            print("Aborted.")
            sys.exit()

    else:
        print("%s option is not supported. Use either [-s] to send to all recipients or [-t] to send to test recipients" % action)

    # save the end time to the stats file
    pymailer._stats("END TIME: %s" % datetime.now())

if __name__ == '__main__':
    main(sys.argv[1:])
