"""Create DNS email records from SES."""
# Third-Party Libraries
import botocore

# khulnasoft-lab Libraries
from api.config import logger
from api.manager import DomainManager
from utils.aws.clients import SES, Route53

domain_manager = DomainManager()
route53 = Route53()
ses = SES()


def manage_resource_records(
    domain_name: str,
    action: str,
    verification_token: str,
):
    """Manage Route53 Records."""
    current_hosted_zones = route53.list_hosted_zones(names_only=True)
    if f"{domain_name}." not in current_hosted_zones:
        logger.error(
            f"{domain_name}. not in current hosted zones ({len(current_hosted_zones)})"
        )
        raise Exception("Domain not in current hosted zones")

    dns_id = "".join(
        hosted_zone.get("Id")
        for hosted_zone in route53.list_hosted_zones()
        if hosted_zone.get("Name") == f"{domain_name}."
    )

    resp = route53.client.change_resource_record_sets(
        HostedZoneId=dns_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": action,
                    "ResourceRecordSet": {
                        "Name": f"_amazonses.{domain_name}",
                        "Type": "TXT",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": f'"{verification_token}"'}],
                    },
                },
                {
                    "Action": action,
                    "ResourceRecordSet": {
                        "Name": domain_name,
                        "Type": "MX",
                        "TTL": 300,
                        "ResourceRecords": [
                            {"Value": "10 inbound-smtp.us-east-1.amazonaws.com"}
                        ],
                    },
                },
            ],
        },
    )
    return resp


def enable_email_receiving(domain_id: str, domain_name: str):
    """Enable receiving emails for a specified domain."""
    domain_manager.update(
        document_id=domain_id,
        data={"is_email_enabled": False, "is_email_pending": True},
    )
    try:
        # Generate verification token
        verification_token = ses.verify_domain_identity_token(domain_name=domain_name)

        manage_resource_records(
            domain_name=domain_name,
            action="UPSERT",
            verification_token=verification_token,
        )

        waiter = ses.client.get_waiter("identity_exists")
        waiter.wait(
            Identities=[domain_name], WaiterConfig={"Delay": 5, "MaxAttempts": 50}
        )

        domain_manager.update(
            document_id=domain_id,
            data={"is_email_active": True, "is_email_pending": False},
        )
    except botocore.exceptions.ClientError as e:
        logger.exception(e)
        domain_manager.update(
            document_id=domain_id,
            data={"is_email_enabled": False, "is_email_pending": False},
        )
    except botocore.exceptions.WaiterError as e:
        logger.exception(e)
        domain_manager.update(
            document_id=domain_id,
            data={"is_email_enabled": False, "is_email_pending": False},
        )
    except Exception as e:
        logger.exception(e)
        if str(e) == "Domain not in current hosted zones":
            domain_manager.update(
                document_id=domain_id,
                data={"is_email_enabled": False, "is_email_pending": False},
            )


def disable_email_receiving(domain_id: str, domain_name: str):
    """Disable receiving emails for a specified domain."""
    domain_manager.update(document_id=domain_id, data={"is_email_pending": True})

    try:
        verification_token = ses.client.get_identity_verification_attributes(
            Identities=[domain_name]
        )["VerificationAttributes"][domain_name]["VerificationToken"]

        manage_resource_records(
            domain_name=domain_name,
            action="DELETE",
            verification_token=verification_token,
        )

        domain_manager.update(
            document_id=domain_id,
            data={"is_email_active": False, "is_email_pending": False},
        )

        ses.client.delete_identity(Identity=domain_name)
    except botocore.exceptions.ClientError as e:
        logger.exception(e)
        domain_manager.update(document_id=domain_id, data={"is_email_pending": False})
