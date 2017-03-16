PyMailer
========
**Simple python bulk mailer script. Raw python using std libs.**

Send bulk html emails from the commandline or in your python script by specifying a database of recipients in csv form, a html template with var placeholders and a subject line.


Requirements
------------

* python >= 3.?

Usage
-----
Setup
~~~~~
Edit the config file before running the script::

    $ vim config.py

Commandline
~~~~~~~~~~~
The simplest method of sending out a bulk email.

Run a test to predefined test_recipients::

    $ ./pymailer --test /path/to/html/file.html /path/to/csv/file.csv 'Email Subject'

Send the actual email to all recipients::

    $ ./pymailer --send /path/to/html/file.html /path/to/csv/file.csv 'Email Subject'

Module Import
~~~~~~~~~~~~~
Alernatively import the PyMailer class into your own code::

    from pymailer import PyMailer
    
    pymailer = PyMailer('/path/to/html/file.html' '/path/to/csv/file.csv' 'Email Subject')
    
    # send a test email
    pymailer.send_test()
    
    # send bulk mail
    pymailer.send()
    
Examples
--------
HTML
~~~~
Example of using placeholders in your html email:

    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
    <html lang="en">
        <body>
            <h1>Test HTML Email - ${name}</h1>
            <p>Hi ${name}, This is a test email from Pymailer - <a href="http://github.com:80/qoda/PyMailer/">http://github.com:80/qoda/PyMailer/</a>.</p>
        </body>
    </html>

Every column of the csv file may be used as a placeholder. Placeolders are for example ${name} or ${title}.
The special columns "reciver" and "sender" are created automatically and contain the complete reciver and sender names,
including the email address.

CSV
~~~
Example of how the csv file should look::

	name,email
    Someones Name,someone@example.com
    Someone Else,someone.else@example.com
    ,some.nameless.person@example.com

The csv file should have a header with column names.
- One column should be 'name' with the complete name of the reciver.
- One column must be 'email' with the email address.
- No column should be called 'receiver' or 'sender', as these are internally used.
