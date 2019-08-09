import boto3
import click

import constants


session = boto3.Session()
ec2 = session.resource('ec2')

@click.group()
def cli():
	"""CLI to manage EC2 snapshots"""


@cli.group('instances')
def instances():
	"""Commands for instances"""


@instances.command('list')
@click.option('--project', default=None, help="Filter instances based on 'project' tag")
def list_instances(project):
	"""List EC2 instances"""
	
	for i in get_ec2_instances(project):
		tags = { t['Key']: t['Value'] for t in i.tags or []}

		print(', '.join([ 
			i.id, 
			i.instance_type, 
			i.placement['AvailabilityZone'], 
			i.state['Name'], 
			i.public_dns_name or '<no public dns name>',
			tags.get(constants.PROJECT_TAG, '<no project>') 
		]))
	#print some default message if no data to show
	return


@instances.command('start')
@click.option('--project', default=None, help="Filter instances based on 'project' tag")
def start_instances(project):
	"""Start EC2 instances"""

	for i in get_ec2_instances(project):
		if i.state['Name'] == constants.STOPPED_STATE:
			print("Starting {0} instance...".format(i.id))
			i.start()
		else:
			print("Skipping {0} instance in {1} state".format(i.id, i.state['Name']))
	
	return


@instances.command('stop')
@click.option('--project', default=None, help="Filter instances based on 'project' tag")
def stop_instances(project):
	"""Stop EC2 instances"""

	for i in get_ec2_instances(project):
		if i.state['Name'] == constants.RUNNING_STATE:
			print("Stopping {0} instance...".format(i.id))
			i.stop()
		else:
			print("Skipping {0} instance in {1} state".format(i.id, i.state['Name']))

	return


@instances.command('snapshot')
@click.option('--project', default=None, help="Filter instances based on 'project' tag")
def create_snapshots(project):
	"""Create snapshots of all volumes"""

	for i in get_ec2_instances(project):
		print("Stopping {0} instance...".format(i.id))
		i.stop()
		i.wait_until_stopped()
		for v in i.volumes.all():
			if has_pending_snapshot(v):
				print("Skipping {0} volume, snapshot already in progress".format(v.id))
			else:
				print("Creating snapshot of {0} volume...".format(v.id))
				v.create_snapshot(Description="Created by EC2 Snapshot Manager")
		print("Starting {0} instance...".format(i.id))
		i.start()
		i.wait_until_running()

	return


@cli.group('volumes')
def volumes():
	"""Commands for EC2 volumes"""


@volumes.command('list')
@click.option('--project', default=None, help="Filter instances based on 'project' tag")
def list_volumes(project):
	"""List volumes for EC2 instaces"""

	for i in get_ec2_instances(project):
		for v in i.volumes.all():
			print(', '.join([
				v.id,
				i.id,
				v.state,
				str(v.size) + ' GiB',
				v.encrypted and "Encrypted" or "Not Encrypted"
			]))
	return


@cli.group('snapshots')
def snapshots():
	"""Commands for EC2 volumes snapshots"""


@snapshots.command('list')
@click.option('--project', default=None, help="Filter instances based on 'project' tag")
@click.option('--all', 'list_all', default=False, is_flag = True, help="List all snapshots for each volume, default is False")
def list_snapshots(project, list_all):
	"""List snapshots for EC2 instances"""

	for i in get_ec2_instances(project):
		for v in i.volumes.all():
			for s in v.snapshots.all():
				print(', '.join([
					s.id,
					v.id,
					i.id,
					s.state,
					s.progress,
					s.start_time.strftime("%x at %X %z")
				]))

				if s.state == constants.COMPLETED_STATE and not list_all:
					break

	return


def get_ec2_instances(project):
	instances = []

	if project:
		filters = [{ 'Name': 'tag:' + constants.PROJECT_TAG, 'Values': [ project ]}]
		instances = ec2.instances.filter(Filters=filters)
	else:
		instances = ec2.instances.all()

	return instances


def has_pending_snapshot(volume):
	snapshots = list(volume.snapshots.all())
	return snapshots and snapshots[0].state == constants.PENDING_STATE
   
	
if __name__ == '__main__':
	cli()