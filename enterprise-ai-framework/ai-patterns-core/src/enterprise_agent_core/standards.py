"""Standard annotations for code lifecycle management.

This module provides decorators to mark features as preview, beta, or stubbed.
These annotations help developers and tooling identify non-stable code.
"""

import functools
import logging
import warnings
from typing import Any, Callable, Optional, Type, Union

# Standard logger for standards/lifecycle events
logger = logging.getLogger(__name__)


class PreviewFeatureWarning(UserWarning):
    """Warning for usage of preview features."""
    pass


class BetaFeatureWarning(UserWarning):
    """Warning for usage of beta features."""
    pass


def preview_feature(
    since: str,
    expected: Optional[str] = None,
    feedback_url: Optional[str] = None
) -> Callable:
    """Mark a class or function as a Preview feature.

    Preview features are experimental and may change or be removed.
    Emits a warning when required.

    Args:
        since: Version when this preview capabilities was introduced
        expected: Expected version for graduation to stable (optional)
        feedback_url: URL to provide feedback (optional)
    """
    def decorator(obj: Union[Type, Callable]) -> Union[Type, Callable]:
        message = f"{obj.__name__} is a PREVIEW feature introduced in v{since}."
        if expected:
            message += f" Targeted for stabilization in v{expected}."
        if feedback_url:
            message += f" Feedback: {feedback_url}"
        
        # Add a _preview_meta attribute for inspection
        setattr(obj, "_preview_meta", {
            "since": since,
            "expected": expected,
            "feedback_url": feedback_url,
            "type": "preview"
        })

        if isinstance(obj, type):
            # For classes, wrap __init__ to warn on instantiation
            original_init = obj.__init__

            @functools.wraps(original_init)
            def new_init(self, *args, **kwargs):
                warnings.warn(message, PreviewFeatureWarning, stacklevel=2)
                logger.info(f"Preview feature instantiated: {message}")
                original_init(self, *args, **kwargs)

            obj.__init__ = new_init
            return obj
        else:
            # For functions/methods
            @functools.wraps(obj)
            def wrapper(*args, **kwargs):
                warnings.warn(message, PreviewFeatureWarning, stacklevel=2)
                logger.debug(f"Preview feature called: {message}")
                return obj(*args, **kwargs)
            return wrapper

    return decorator


def beta(since: str) -> Callable:
    """Mark a class or function as Beta.

    Beta features are mostly stable but API surface may change.
    
    Args:
        since: Version when this entered beta
    """
    def decorator(obj: Union[Type, Callable]) -> Union[Type, Callable]:
        message = f"{obj.__name__} is in BETA since v{since}. API subject to minor changes."
        
        setattr(obj, "_beta_meta", {
            "since": since,
            "type": "beta"
        })
        
        # We generally don't warn for Beta, just log if needed, or leave as marker
        if isinstance(obj, type):
            original_init = obj.__init__
            @functools.wraps(original_init)
            def new_init(self, *args, **kwargs):
                logger.debug(f"Beta feature instantiated: {message}")
                original_init(self, *args, **kwargs)
            obj.__init__ = new_init
            return obj
        else:
            @functools.wraps(obj)
            def wrapper(*args, **kwargs):
                # No warning for beta, just documentation/metadata
                return obj(*args, **kwargs)
            return wrapper

    return decorator


def stub(reason: str) -> Callable:
    """Mark a class or function as a Stub.

    Indicates incomplete implementation.
    
    Args:
        reason: Explanation of what is missing
    """
    def decorator(obj: Union[Type, Callable]) -> Union[Type, Callable]:
        message = f"{obj.__name__} is a STUB. {reason}"
        
        setattr(obj, "_stub_meta", {
            "reason": reason,
            "type": "stub"
        })

        if isinstance(obj, type):
            original_init = obj.__init__
            @functools.wraps(original_init)
            def new_init(self, *args, **kwargs):
                logger.warning(message)
                original_init(self, *args, **kwargs)
            obj.__init__ = new_init
            return obj
        else:
            @functools.wraps(obj)
            def wrapper(*args, **kwargs):
                logger.warning(message)
                return obj(*args, **kwargs)
            return wrapper

    return decorator
