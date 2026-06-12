from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.current_user import CurrentUser
from app.models.execution import TaskExecution
from app.models.task import TaskDefinition
from app.models.user import User


def get_dashboard_summary(db: Session, user: CurrentUser | User) -> dict:
    task_count = db.query(func.count(TaskDefinition.id)).scalar() or 0
    execution_query = db.query(TaskExecution)
    if not user.has_role("ADMIN"):
        execution_query = execution_query.filter(TaskExecution.requested_by_email == user.email)

    statuses = {
        row[0]: row[1]
        for row in execution_query.with_entities(
            TaskExecution.execution_status, func.count(TaskExecution.id)
        )
        .group_by(TaskExecution.execution_status)
        .all()
    }
    latest = execution_query.order_by(TaskExecution.requested_at.desc()).limit(5).all()
    return {
        "taskCount": task_count,
        "executionStatusSummary": statuses,
        "latestExecutions": [
            {
                "id": item.id,
                "taskName": item.task.display_name,
                "status": item.execution_status,
                "requestedAt": item.requested_at,
                "resultSummary": item.result_summary,
            }
            for item in latest
        ],
    }
