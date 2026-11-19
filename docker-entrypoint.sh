#!/bin/sh

set -e

if [ "$FEED_LOG_QUIET" != "true" ]; then
    sed -i -r "s/--quiet/ /" /etc/s6/update-daemon/run
else
    sed -i -r "s/\.php/.php --quiet/" /etc/s6/update-daemon/run
fi

if [ -n "$DB_USER_FILE" ]; then DB_USER="$(cat $DB_USER_FILE)"; fi

if [ -n "$DB_PASS_FILE" ]; then DB_PASS="$(cat $DB_PASS_FILE)"; fi

sh /wait-for.sh $DB_HOST:$DB_PORT -- php /initialize.php && s6-setuidgid nobody php /var/www/update.php --update-schema=force-yes && exec s6-svscan /etc/s6/

exec "$@"
