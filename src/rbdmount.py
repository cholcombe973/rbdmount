#!/usr/bin/python2.7

import optparse
import os
import os.path
import re
import sys
import subprocess
from subprocess import PIPE
try:
	from rtslib import *
except ImportError:
	print 'Please install targetutils to get the rtslib'

def is_valid_wwn(wwn):
	if re.match("naa\.[0-9A-Fa-f]{16}$", wwn):
		return True
	return False

class RbdMount:
	pool     		= None
	device 			= None
	rbd_id 			= None
	rbd_wwn			= None
	image_name 		= None
	target_wwn 		= None
	initiator_wwn	= []
	
	def __init__(self,pool,device,rbd_id,rbd_wwn,image_name,target,initiator):
		if pool is not None:		
			self.pool = pool.rstrip('\n')
		if rbd_wwn is not None:
			rbd_wwn = rbd_wwn.rstrip('\n')
			if is_valid_wwn(rbd_wwn):
				self.rbd_wwn = rbd_wwn
			else:
				print 'Bad rbd wwn: ' + rbd_wwn + ' for device: ' + image_name
		if device is not None:		
			self.device = device.rstrip('\n')
		self.rbd_id = rbd_id
		if image_name is not None:		
			self.image_name = image_name.rstrip('\n')
		if target is not None:		
			self.target_wwn = target.rstrip('\n')
		self.initiator_wwn = initiator
		
def parse_config(c):
	rbd_list = []
	i = 1
	if not os.path.exists(c):
		    sys.exit(-1)

	f = open(c,'r').readlines()	
	for l in f:
	    #Skip comments
	    if not l.startswith('#'):
			parts = l.split(',')
			if len(parts) >= 5:
				#                        pool,device,rbd_id,rbd_wwn,image_name,target,initiator[]
				rbd_list.append(RbdMount(parts[2],None,i,parts[0],parts[1],parts[3],parts[4].split('|')))
				i = i+1
			else:
				print 'Skipping: ' + l + ' due to bad formatting'
	return rbd_list

def check_configfs():
	if not os.path.ismount('/sys/kernel/config'):
		print 'Configfs is not mounting.  Attempting to correct..'
		print 'You will want to try to stop and start /etc/init.d/target to see if it works correctly after this'
		subprocess.Popen("mount -t configfs configfs /sys/kernel/config/",shell=True).wait()
		print 'Exiting.  After target is confirmed to work please rerun this script'
		sys.exit(-1)
	else:
		print 'Configfs is properly mounted.'

def check_qlini_mode():
	status = subprocess.Popen("cat /sys/module/qla2xxx/parameters/qlini_mode",shell=True,stdout=PIPE).communicate()
	if status[0].rstrip('\n') == "enabled":
		#I can't setup targets in enabled mode.
		#rmmod and modprobe qla2xxx again.  This is a weird bug
		subprocess.Popen("/etc/init.d/target stop",shell=True).wait()
		subprocess.Popen("rmmod qla2xxx",shell=True).wait()
		subprocess.Popen("modprobe qla2xxx",shell=True).wait()
		subprocess.Popen("/etc/init.d/target start",shell=True).wait()
	else:
			print 'Qlini mode is disabled.  Proceeding forward'

'''
	This function will check target-utils to confirm
	whether or not a target exists.  Returns True or False respectively.

'''
def checkTargetExists(t_name):
	match = False
	r = root.RTSRoot()
	x = r.storage_objects
	for i in x:
		if t_name == i.name:
			match = True
	return match

def createTarget(lun_id,lun_wwn,name,dev_path,acl_wwn,fabric_wwn):
	#acl_wwn[] could have multiple values.  Map each to the same lun

	#Check to see if the target exists already in case someone reruns the script with the wrong params
	if not checkTargetExists(name):
		print 'Creating target: "' + str(lun_id) + '" "' + name+ '" "' + dev_path + '" "' + acl_wwn[0].rstrip('\n') + '" "' + fabric_wwn + '"'
		backstore = IBlockBackstore(lun_id, mode='create')
		try:
			so = IBlockStorageObject(backstore, name, dev=dev_path, gen_wwn=False)
			so._set_wwn(lun_wwn)
		except:
			backstore.delete()
			raise

		# Create an FC target endpoint using a qla2xxx WWPN
		fabric = FabricModule('qla2xxx')
		target = Target(fabric, fabric_wwn)
		tpg = TPG(target,1)	

		# Export LUN id# via the 'so' StorageObject class
		# Setup the NodeACL for an FC initiator, and create MappedLUN 0
		map_lun = tpg.lun(lun_id, so, name)

		for a in acl_wwn:
			a = a.rstrip('\n')
			print 'Creating the node_acl'
			node_acl = NodeACL(tpg, a, mode="any")
			print node_acl
			print 'Mapping the lun to node_acl'
			MappedLUN(node_acl, map_lun.lun, map_lun.lun, write_protect=False)
	else:
		print 'Target already exists, skipping'
def get_mapped(orig_rbds):
	#this list needs to be merged with the original rbds we mounted to add the device location
	#rbd_list = []
	mapped = subprocess.Popen("rbd showmapped | tail -n +2 | awk '{print $3 \" \" $5}'",shell=True,stdout=PIPE).communicate()
	for m in mapped[0].split('\n'):
		if m is not "":
			parts = m.split(' ')
			for x in orig_rbds:
				print 'Comparing: ' + x.image_name + ' to: ' + parts[0]
				if x.image_name == parts[0]:
					x.device = parts[1].rstrip('\n')
					print 'updating: ' + x.device						
	return orig_rbds

def rbd_mount(rbd):
	print 'mapping: ' +  rbd.image_name
	subprocess.Popen("rbd map " + rbd.image_name + " --pool " + rbd.pool,shell=True).wait()	

def main():
	parser = optparse.OptionParser(usage="usage: %prog [options] arg", version="%prog 1.0")
	parser.add_option("-c", dest="config",help="Config file containing mount points")
	parser.add_option("-a", dest="add",help=" *Optional* Add a rbd mount at runtime.  Specify the mount name in the config file. Example rbdmount.py -c /etc/ceph/mounts -a dvmesx01j_lun1")

    #parse the command line arguments and see what we got
	(opts, args) = parser.parse_args()

	if opts.config is None:
		print "-c config option is missing"
		parser.print_help()
		sys.exit(-1)
	#ff -a is specified we can assume the system is already up and running properly
	if opts.add is not None:
		print 'Adding mount at runtime'
		#check that the rbd specified exists in the list
		csc_rbds = parse_config(opts.config)
		for r in csc_rbds:
			if r.image_name == opts.add:
				#mount it up
				rbd_mount(r)
				#Figure out where it was mapped to
				mapped_rbds = get_mapped(csc_rbds)
				for m in mapped_rbds:
					#only map our new rbd
					if m.image_name == opts.add:						
						if m.device is not None:
							createTarget(m.rbd_id,m.rbd_wwn,m.image_name,m.device,m.initiator_wwn,m.target_wwn)
							sys.exit(0)
						else:
							print 'Could not map: ' + m.image_name + ' because of missing mount point'
							sys.exit(-1)	
	else:
		check_qlini_mode()
		check_configfs()
		csc_rbds = parse_config(opts.config)
		for r in csc_rbds:
			rbd_mount(r) #check the mounts first on startup
		#Figure out where they were mapped to
		mapped_rbds = get_mapped(csc_rbds)
		for m in mapped_rbds:
			if m.device is not None:				
				createTarget(m.rbd_id,m.rbd_wwn,m.image_name,m.device,m.initiator_wwn,m.target_wwn)
			else:
				print 'Could not map: ' + m.image_name + ' because of missing mount point'
if __name__ == "__main__":
    main()
