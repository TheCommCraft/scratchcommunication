"""
Create multiple cloud connections at once
"""
from scratchcommunication import CloudConnection, TwCloudConnection, Session, Sky
from typing import Sequence, Mapping, Any, Optional

def scratch_and_turbowarp_connection(
    project_id : int,
    *,
    session : Session,
    as_sky : bool = False,
    args : Optional[Sequence] = None,
    kwargs : Optional[Mapping[str, Any]] = None
) -> tuple[CloudConnection, CloudConnection]:
    """
    Create a turbowarp connection with a normal one.
    """
    assert not as_sky
    args = tuple(args or ())
    kwargs = dict(kwargs or {})
    cloud_1 = session.create_cloudconnection(project_id, *args, **kwargs)
    cloud_2 = session.create_tw_cloudconnection(project_id, *args, **kwargs)
    return (cloud_1, cloud_2)

def multiple_scratch_connections(
    project_ids : Sequence[int],
    *,
    session : Session,
    as_sky : bool = False,
    args : Optional[Sequence] = None,
    kwargs : Optional[Mapping[str, Any]] = None
) -> tuple[CloudConnection, ...]:
    """
    Create many normal connections.
    """
    assert not as_sky
    args = tuple(args or ())
    kwargs = dict(kwargs or {})
    clouds = tuple(session.create_cloudconnection(project_id, *args, **kwargs) for project_id in project_ids)
    return clouds

def multiple_scratch_and_turbowarp_connections(
    project_ids : Sequence[int],
    *,
    session : Session,
    as_sky : bool = False,
    args : Optional[Sequence] = None,
    kwargs : Optional[Mapping[str, Any]] = None
) -> tuple[CloudConnection, ...]:
    """
    Create many normal connections with turbowarp ones.
    """
    assert not as_sky
    args = tuple(args or ())
    kwargs = dict(kwargs or {})
    clouds = tuple(session.create_cloudconnection(project_id, *args, **kwargs) for project_id in project_ids) + \
        tuple(session.create_tw_cloudconnection(project_id, *args, **kwargs) for project_id in project_ids)
    return clouds
