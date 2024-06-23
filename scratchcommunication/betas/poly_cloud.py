"""
Create multiple cloud connections at once
"""
from scratchcommunication import CloudConnection, TwCloudConnection, Session, Sky
from typing import Sequence, Mapping, Any

def scratch_and_turbowarp_connection(
    project_id : int,
    *,
    session : Session,
    as_sky : bool = False,
    args : Sequence = None,
    kwargs : Mapping[str, Any] = None
) -> tuple[CloudConnection, CloudConnection]:
    """
    Create a turbowarp connection with a normal one.
    """
    args = args or ()
    kwargs = kwargs or {}
    cloud_1 = session.create_cloudconnection(project_id=project_id, *args, **kwargs)
    cloud_2 = session.create_tw_cloudconnection(project_id=project_id, *args, **kwargs)
    if as_sky:
        return Sky(cloud_1, cloud_2)
    return (cloud_1, cloud_2)

def multiple_scratch_connections(
    project_ids : Sequence[int],
    *,
    session : Session,
    as_sky : bool = False,
    args : Sequence = None,
    kwargs : Mapping[str, Any] = None
) -> tuple[CloudConnection]:
    """
    Create many normal connections.
    """
    args = args or ()
    kwargs = kwargs or {}
    clouds = tuple(session.create_cloudconnection(project_id=project_id, *args, **kwargs) for project_id in project_ids)
    if as_sky:
        return Sky(*clouds)
    return clouds

def multiple_scratch_and_turbowarp_connections(
    project_ids : Sequence[int],
    *,
    session : Session,
    as_sky : bool = False,
    args : Sequence = None,
    kwargs : Mapping[str, Any] = None
) -> tuple[CloudConnection]:
    """
    Create many normal connections with turbowarp ones.
    """
    args = args or ()
    kwargs = kwargs or {}
    clouds = tuple(session.create_cloudconnection(project_id=project_id, *args, **kwargs) for project_id in project_ids) + \
        tuple(session.create_tw_cloudconnection(project_id=project_id, *args, **kwargs) for project_id in project_ids)
    if as_sky:
        return Sky(*clouds)
    return clouds
