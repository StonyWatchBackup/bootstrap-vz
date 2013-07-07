from base import Task
from common import phases
from common.exceptions import TaskError
from connection import Connect
from filesystem import UnmountVolume
import time


class CreateVolume(Task):
	phase = phases.volume_creation
	after = [Connect]

	description = 'Creating an EBS volume for bootstrapping'

	def run(self, info):
		volume_size = int(info.manifest.volume['size']/1024)

		info.volume = info.connection.create_volume(volume_size, info.host['availabilityZone'])
		while info.volume.volume_state() != 'available':
			time.sleep(5)
			info.volume.update()


class AttachVolume(Task):
	phase = phases.volume_creation
	after = [CreateVolume]

	description = 'Attaching the EBS volume'

	def run(self, info):
		def char_range(c1, c2):
			"""Generates the characters from `c1` to `c2`, inclusive."""
			for c in xrange(ord(c1), ord(c2)+1):
				yield chr(c)

		import os.path
		info.bootstrap_device = {}
		for letter in char_range('f', 'z'):
			dev_path = os.path.join('/dev', 'xvd' + letter)
			if not os.path.exists(dev_path):
				info.bootstrap_device['path'] = dev_path
				info.bootstrap_device['ec2_path'] = os.path.join('/dev', 'sd' + letter)
				break
		if 'path' not in info.bootstrap_device:
			raise VolumeError('Unable to find a free block device path for mounting the bootstrap volume')

		info.volume.attach(info.host['instanceId'], info.bootstrap_device['ec2_path'])
		while info.volume.attachment_state() != 'attached':
			time.sleep(2)
			info.volume.update()


class DetachVolume(Task):
	phase = phases.volume_unmounting
	after = [UnmountVolume]

	description = 'Detaching the EBS volume'

	def run(self, info):
		info.volume.detach()
		while info.volume.attachment_state() is not None:
			time.sleep(2)
			info.volume.update()


class DeleteVolume(Task):
	phase = phases.cleaning
	after = []

	description = 'Deleting the EBS volume'

	def run(self, info):
		info.volume.delete()
		del info.volume


class VolumeError(TaskError):
	pass