import urllib.request
import json
import os

def create_dashboard():
    url = "https://raw.githubusercontent.com/SigNoz/dashboards/main/llm-observability/sample-chatpdf-cost-dashboard.json"
    print("Downloading dashboard template from SigNoz repository...")
    response = urllib.request.urlopen(url)
    raw_content = response.read().decode()
    
    # Translate metrics to modern OpenInference standard attributes
    raw_content = raw_content.replace("llm.usage.prompt_tokens", "llm.token_count.prompt")
    raw_content = raw_content.replace("llm.usage.completion_tokens", "llm.token_count.completion")
    raw_content = raw_content.replace("llm.usage.total_tokens", "llm.token_count.total")
    
    dashboard = json.loads(raw_content)

    # 1. Update Title and metadata
    dashboard["title"] = "SigNoz AI Agent Observability Dashboard"
    dashboard["name"] = "agent_observability_dashboard"
    
    # 2. Update default service name variable
    variables = dashboard.get("variables", {})
    for var_id, var_config in variables.items():
        if var_config.get("name") == "serviceName":
            var_config["selectedValue"] = "knowledge-share-agents"
            print(f"Updated default service name variable to 'knowledge-share-agents'.")

    # 3. Update widgets
    widgets = dashboard.get("widgets", [])
    for w in widgets:
        title = w.get("title", "")
        
        # Customize Widget 0: User Token -> Agent Persona Token
        if "User Token" in title:
            w["title"] = "Token Consumption by Agent Persona"
            # Update GroupBy and Filter fields
            query_data = w.get("query", {}).get("builder", {}).get("queryData", [])
            for qd in query_data:
                # Replace group by fields
                qd["groupBy"] = [
                    {
                        "dataType": "string",
                        "id": "agent_id--string--tag--false",
                        "isColumn": False,
                        "isJSON": False,
                        "key": "agent_id",
                        "type": "tag"
                    }
                ]
                # Replace order by column name to match the legend
                if qd["expression"] == "A":
                    qd["orderBy"] = [{"columnName": "sum(llm.token_count.completion)", "order": "desc"}]
                    qd["filter"]["expression"] = "serviceName IN $serviceName agent_id EXISTS"
                elif qd["expression"] == "B":
                    qd["orderBy"] = [{"columnName": "sum(llm.token_count.prompt)", "order": "desc"}]
                    qd["filter"]["expression"] = "serviceName IN $serviceName agent_id EXISTS"
                elif qd["expression"] == "C":
                    qd["orderBy"] = [{"columnName": "sum(llm.token_count.total)", "order": "desc"}]
                    qd["filter"]["expression"] = "serviceName IN $serviceName agent_id EXISTS"
            print("Configured Widget 0: Token Consumption by Agent Persona.")

        # Customize Widget 1: Estimated Cost (GPT-4) -> Estimated Cost (GPT-4o-mini)
        elif "Estimated Costs" in title:
            w["title"] = "Estimated Costs (Last 24h) - GPT-4o-mini"
            # GPT-4o-mini pricing: $0.15 / 1M input tokens, $0.60 / 1M output tokens
            # Formula: (PromptTokens * 0.15 + CompletionTokens * 0.60) / 1,000,000
            query_formulas = w.get("query", {}).get("builder", {}).get("queryFormulas", [])
            for qf in query_formulas:
                qf["expression"] = "(A * 0.15)/1000000 + (B * 0.60)/1000000"
            print("Configured Widget 1: Estimated Costs (Last 24h).")

        # Customize Widget 2: Cost Over Time
        elif "Cost Over Time" in title:
            w["title"] = "GPT-4o-mini Cost Over Time"
            query_formulas = w.get("query", {}).get("builder", {}).get("queryFormulas", [])
            for qf in query_formulas:
                qf["expression"] = "(A * 0.15)/1000000 + (B * 0.60)/1000000"
            print("Configured Widget 2: Cost Over Time.")

    # 4. Save to signoz_dashboard.json
    output_path = "signoz_dashboard.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, indent=2)
    print(f"Custom dashboard written to '{os.path.abspath(output_path)}'.")

if __name__ == "__main__":
    create_dashboard()
