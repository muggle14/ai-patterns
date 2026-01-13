"""Telemetry module for Enterprise Agent observability.

Provides OpenTelemetry-based tracing with standard span names
and attributes for the cognitive loop.
"""

import os
import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

from .attributes import Attributes
from .spans import SpanNames, agent_span, create_tracer

logger = logging.getLogger(__name__)

__all__ = [
    "Attributes",
    "SpanNames",
    "agent_span",
    "create_tracer",
    "configure_telemetry",
]


def configure_telemetry(
    service_name: str = "enterprise_agent_core",
    exporter_type: Optional[str] = None,
) -> TracerProvider:
    """Configure OpenTelemetry for Azure AI Foundry.

    Sets up tracing with the appropriate exporter based on environment
    configuration or explicit parameter.

    Args:
        service_name: Name of the service for tracing
        exporter_type: Exporter to use (azure_monitor, otlp, console, none)
                      If not specified, reads from TRACING_EXPORTER env var

    Returns:
        Configured TracerProvider

    Environment Variables:
        TRACING_EXPORTER: Exporter type (azure_monitor, otlp, console, none)
        APPLICATIONINSIGHTS_CONNECTION_STRING: Required for azure_monitor
        OTEL_EXPORTER_OTLP_ENDPOINT: Required for otlp exporter
    """
    # Create resource with service name
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    # Determine exporter type
    exp_type = exporter_type or os.environ.get("TRACING_EXPORTER", "none")

    if exp_type == "azure_monitor":
        _configure_azure_monitor(provider)
    elif exp_type == "otlp":
        _configure_otlp(provider)
    elif exp_type == "console":
        _configure_console(provider)
    elif exp_type != "none":
        logger.warning(f"Unknown exporter type: {exp_type}, tracing disabled")

    # Set as global provider
    trace.set_tracer_provider(provider)

    logger.info(f"Telemetry configured with exporter: {exp_type}")
    return provider


def _configure_azure_monitor(provider: TracerProvider) -> None:
    """Configure Azure Monitor exporter for Application Insights."""
    conn_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")

    if not conn_string:
        logger.warning(
            "APPLICATIONINSIGHTS_CONNECTION_STRING not set, "
            "Azure Monitor exporter disabled"
        )
        return

    try:
        from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

        exporter = AzureMonitorTraceExporter(connection_string=conn_string)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("Azure Monitor exporter configured")
    except ImportError:
        logger.warning(
            "azure-monitor-opentelemetry-exporter not installed. "
            "Install with: pip install azure-monitor-opentelemetry-exporter"
        )


def _configure_otlp(provider: TracerProvider) -> None:
    """Configure OTLP exporter for generic OpenTelemetry collectors."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")

    if not endpoint:
        logger.warning(
            "OTEL_EXPORTER_OTLP_ENDPOINT not set, OTLP exporter disabled"
        )
        return

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info(f"OTLP exporter configured for endpoint: {endpoint}")
    except ImportError:
        logger.warning(
            "opentelemetry-exporter-otlp not installed. "
            "Install with: pip install opentelemetry-exporter-otlp"
        )


def _configure_console(provider: TracerProvider) -> None:
    """Configure console exporter for local development."""
    exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    logger.info("Console exporter configured (development mode)")
