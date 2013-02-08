rbdmount
========

Ceph Rados Block Device Auto Mount

Python code that will automatically mount ceph rados block devices and export them over LIO fibre channel utils.

Things to note:<br>
1. VMware requires an identical lun WWN so it can failover to each fabric seamlessly.  
2. I have created a tool which will generate unique wwn's. It is called wwngen.py  
3. The /etc/ceph/mounts file allows you to export a lun to multiple initiators.  There are examples in the file of this. 

Usage: rbdmount.py -c /etc/ceph/mounts

Alternate Usage to add only 1 lun at runtime: rbdmount.py -c /etc/ceph/mounts -a dvmesx01_lun1

Config file format:

rbd_name,pool,target_wwn,initiator_wwn's separated by | 
naa.60014054bfa5d41a,server01_lun1,vmware,21:01:00:e0:8b:bd:1e:c0,10:00:00:00:c9:e0:09:8c|10:00:00:00:c9:e0:4a:18
