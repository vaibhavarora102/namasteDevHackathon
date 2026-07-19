import os
import logging
from dotenv import load_dotenv
from opentelemetry import trace

# Load environment variables from .env file
load_dotenv()
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger("telemetry")
logging.basicConfig(level=logging.INFO)

def init_telemetry():
    enable_telemetry = os.getenv("ENABLE_TELEMETRY", "false").lower() == "true"
    if not enable_telemetry:
        print("[Telemetry] Telemetry is disabled (ENABLE_TELEMETRY != true)")
        logger.info("Telemetry is disabled (ENABLE_TELEMETRY != true)")
        return

    signoz_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    service_name = os.getenv("OTEL_SERVICE_NAME", "knowledge-share-agents")

    print(f"[Telemetry] Initializing telemetry for service '{service_name}' pointing to SigNoz endpoint '{signoz_endpoint}'...")
    logger.info(f"Initializing telemetry for service '{service_name}' pointing to SigNoz endpoint '{signoz_endpoint}'...")

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from openinference.instrumentation.langchain import LangChainInstrumentor

        resource = Resource.create(attributes={
            "service.name": service_name
        })

        # --- Configure Tracing ---
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=signoz_endpoint, insecure=True)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        # --- Configure Logging ---
        try:
            from opentelemetry._logs import set_logger_provider
            from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
            from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
            try:
                from opentelemetry.exporter.otlp.proto.grpc.log_exporter import OTLPLogExporter
            except ImportError:
                from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

            logger_provider = LoggerProvider(resource=resource)
            set_logger_provider(logger_provider)
            log_exporter = OTLPLogExporter(endpoint=signoz_endpoint, insecure=True)
            logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
            
            # Attach OTel handler to standard logging root
            handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
            logging.getLogger().addHandler(handler)
            print("[Telemetry] OpenTelemetry Logging Handler successfully initialized.")
        except Exception as log_err:
            print(f"[Telemetry] Logging setup warning: {log_err}")

        # Instrument LangChain to capture agent chains, LLM calls, and retrievals automatically
        LangChainInstrumentor().instrument()
        print("[Telemetry] OpenTelemetry & LangChain instrumentor successfully initialized.")
        logger.info("OpenTelemetry & LangChain instrumentor successfully initialized.")
    except Exception as e:
        print(f"[Telemetry] Failed to initialize OpenTelemetry: {e}")
        logger.error(f"Failed to initialize OpenTelemetry: {e}", exc_info=True)


# Run telemetry initialization
init_telemetry()
