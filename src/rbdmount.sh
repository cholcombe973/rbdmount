#!/bin/bash
#
# Filename:  /etc/init.d/rbd
# rbd:	Mount/Unmount ceph rbd exports
#
# Bring up/down rbd exports
#
# chkconfig: 2345 18 01
# description:	rbd
#
#########################################################################
#
MODNAME="rbd"
DEBUG=0
LOGFILE=/var/log/rbd.dbug
CONFIGFILE=/etc/rbd/mounts


if [ $DEBUG != 0 ]; then
	echo "$0 $*" >> $LOGFILE
fi


function load_rbd_mod() {
	echo -n $"Loading rbd: "
	modprobe -q ${MODNAME} > /dev/null
	RETVAL=$?
	if [ $RETVAL == 0 ]; then
		echo "  [OK]"
	else
		echo "  [FAILED]: $RETVAL"
	fi

	return 0
}
start () {
if test "x `lsmod | grep ${MODNAME} | awk '{ if ($$1 == "${MODNAME}") print $$1 }'`" == x ; 
	then
		load_rbd_mod()

		if [ -d ${TCM_CFS_DIR} ]; then
			echo -n $"Calling START $0 "
			RETVAL=1
			echo "ERROR, target_core_mod/ConfigFS already active"
			return $RETVAL
		fi
}
stop () {
	rm -f ${SEMA_TARGET}

	unload_tcm_mod
	RET=$?
	if [ $RET != 0 ]; then
		return 1
	fi
	sleep 1

	rm -f ${LOCK_TARGET}
	echo "Successfully unloaded target_core_mod/ConfigFS core"
	return $RET
}

restart () {
	stop 1
	start 0
	RETVAL=$?
}

case "$1" in
	start)
		start 0
		;;
	stop)
		stop 1
		;;
	status)
		tcm_status
		RETVAL=$?
		;;
	restart|reload|force-reload)
		restart 1
		;;
	*)
		echo $"Usage: $0 {start|stop|status|restart}"
		exit 1
esac

exit $?

