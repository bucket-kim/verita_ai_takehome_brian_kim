"""
Test 8: Audit log immutability - attempt to UPDATE or DELETE AuditLog
Should raise PermissionError as defined in model's save/delete methods
"""
import pytest
from apps.ops.models import AuditLog


@pytest.mark.django_db
def test_audit_log_cannot_be_updated():
    """Test that AuditLog entries cannot be modified after creation."""
    # Create an audit log entry
    log = AuditLog.objects.create(
        entity_type='TestEntity',
        entity_id='123',
        action='created',
        actor='test_user',
        before_value=None,
        after_value={'field': 'value'},
        reason='Test reason'
    )

    # Attempt to update it - should raise PermissionError
    log.reason = 'Modified reason'

    with pytest.raises(PermissionError, match="cannot be modified"):
        log.save()


@pytest.mark.django_db
def test_audit_log_cannot_be_deleted():
    """Test that AuditLog entries cannot be deleted."""
    # Create an audit log entry
    log = AuditLog.objects.create(
        entity_type='TestEntity',
        entity_id='456',
        action='deleted',
        actor='test_user',
        before_value={'field': 'old_value'},
        after_value=None,
        reason='Test deletion'
    )

    # Attempt to delete it - should raise PermissionError
    with pytest.raises(PermissionError, match="cannot be deleted"):
        log.delete()

    # Verify it still exists
    assert AuditLog.objects.filter(id=log.id).exists()
