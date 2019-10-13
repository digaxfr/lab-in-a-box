# Notes

Random notes here and there...

# VMware

When you install ESXi, ```vmk0``` will use the MAC address of the default NIC. You must reset config of the ESXi host on next boot to create the golden image. This will reset ```vmk0```.

Refer to https://kb.vmware.com/s/article/1031111
