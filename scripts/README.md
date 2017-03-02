# A few funny/handy scripts

## PC turned on

In order for this script to work, move it to the root folder of this repo.

```bash
mv scripts/script-pc-turned-on.py ./
```

Then, in `/etc/rc.local`, add the following right above `exit 0`:

```bash
su - someuser -c /whatever/commandline.sh &
```

where `/whatever/commandline.sh` contains:

```bash
#!/bin/sh

python3 path-to-python-mailer/script-pc-turned-on.py
```

**Don't forget to replace `someuser` with your real username.**
