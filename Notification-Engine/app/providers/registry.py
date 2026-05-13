from app.models.notification import ChannelType
from app.providers.base import NotificationProvider
from app.providers.email import EmailProvider
from app.providers.push import PushProvider
from app.providers.sms import SmsProvider

_registry: dict[ChannelType, NotificationProvider] = {
    ChannelType.EMAIL: EmailProvider(),
    ChannelType.SMS: SmsProvider(),
    ChannelType.PUSH: PushProvider(),
}


def get_provider(channel: ChannelType) -> NotificationProvider:
    try:
        return _registry[channel]
    except KeyError as e:
        raise ValueError(f"Unsupported channel: {channel}") from e
