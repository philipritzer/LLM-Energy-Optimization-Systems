import base64
import functools
import os
import warnings
from io import BytesIO

import streamlit as st
from langchain.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_experimental.tools import PythonREPLTool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

import auth_keys
from shared_utils import (agent_node, get_weather_forecast, AgentState, create_agent, weather_state_update,
                          format_response, get_summed_historic_data, get_live_data, energy_optimizer)

warnings.filterwarnings("ignore")

os.environ["OPENAI_API_KEY"] = auth_keys.openai_api_key
os.environ["OPENWEATHERMAP_API_KEY"] = auth_keys.openweather_api_key

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = auth_keys.langchain_api_key
os.environ["LANGCHAIN_PROJECT"] = "multi_agent"

llm = ChatOpenAI(model='gpt-4o', temperature=0)

python_repl_tool = PythonREPLTool()

analyzers = ["Weather Retriever", "Coder"]
nodes = analyzers + ["Energy optimizer"]
system_prompt = (
    f"""You are the Supervisor. Your task is to manage the conversation between the nodes and decide which node 
    should be called next.

Follow these guidelines:

If the user asks about the current weather or a weather forecast, route the request to the Weather Retriever. If the 
user requests data on energy production, consumption, or grid interaction of the solar panel system, 
or any visualization route the request to the Coder. If the user needs specific optimization suggestions regarding 
energy usage, route the request to the Energy optimizer. If the user's request does not clearly fit into any of the 
above categories, decide based on the context which node can provide the most appropriate response. If you can't 
decide chose the Energy optimizer. If the question has nothing to do with any topic or no additional data is required 
select Energy optimizer If there is a question about any energy usage intense task check the weather to plan that 
task If additional data is required select one of: {analyzers}

You can chose between {nodes}
     """
)
options = nodes

function_def = {
    "name": "route",
    "description": "Select the next role.",
    "parameters": {
        "title": "routeSchema",
        "type": "object",
        "properties": {
            "next": {
                "title": "Next",
                "anyOf": [
                    {"enum": options},
                ],
            }
        },
        "required": ["next"],
    },
}

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
        (
            "system",
            "Given the conversation above, who should act next?"
            "If the question has nothing to do with any topic select Energy optimizer "
            "If no additional data is required to answer the question select Energy optimizer "
            "If additional data is required select one of: {options}",
        ),
    ]
).partial(options=str(options), members=", ".join(nodes))

supervisor_chain = (
        prompt
        | llm.bind_functions(functions=[function_def], function_call="route")
        | JsonOutputFunctionsParser()
)

weather_retriever = create_agent(llm, [get_weather_forecast],
                                 """You are the Weather Retriever. Your task is to provide the current weather and 
                                 the weather forecast for a predefined location.""")
weather_retriever_node = functools.partial(weather_state_update, agent=weather_retriever, name="Weather Retriever")

code_agent = create_agent(llm, [python_repl_tool, get_summed_historic_data, get_live_data],
                          "You may generate safe Python code to analyze data and generate charts using matplotlib. If "
                          "your task ist to plot solar data you can request time series data with python from the "
                          "endpoint <insert url here> "
                          "it returns the solar data in csv format. The data covers the last three days "
                          "and includes the following keys: production (in kWh), grid (in kWh), consumption (in kWh), "
                          "timestamp, battery_status (in %). The timestamp is formatted as follows: "
                          "YYYY-MM-DDTHH:MM:SS. \n. Don't use double quotes in the code \n"
                          "  Answer only with your results and never ask follow up questions.")
code_node = functools.partial(agent_node, agent=code_agent, name="Coder")

analyze_agent = create_agent(llm, [energy_optimizer],
                             """You are an energy optimizer. You analyze solar and weather data to provide insights 
                             on energy usage and optimization. This includes identifying non-optimal energy usage 
                             periods, suggesting optimal times for high energy consumption based on solar production 
                             and weather forecast, and offering general energy-saving recommendations. Energy from 
                             the solar panel is free, so always prioritize power coming from the solar panel. 
                             Recommend times where the sun is shining for energy-intensive tasks to utilize the free 
                             energy from the solar panel. When analyzing the data, consider the following hierarchy 
                             of factors: Solar Production: Prioritize recommendations based on periods with the 
                             highest expected solar energy production. Weather Conditions: Consider weather 
                             conditions such as cloud cover and precipitation that affect solar production. 
                             Temperature: Suggest energy-intensive tasks during periods with favorable temperatures, 
                             if solar production is insufficient. When you receive information from the coder, 
                             repeat it and analyze it according to the above factors. Please give tips on how to 
                             analyze a visualization if the coder responded with a visualization. Don't interact with 
                             the coder or weather retriever, just pass the information as it would be yours.""")
analyze_node = functools.partial(agent_node, agent=analyze_agent, name="Energy optimizer")

graph = StateGraph(AgentState)

graph.add_node("Weather Retriever", weather_retriever_node)
graph.add_node("Coder", code_node)
graph.add_node("Energy optimizer", analyze_node)
graph.add_node("supervisor", supervisor_chain)

for analyzer in analyzers:
    graph.add_edge(analyzer, "supervisor")

conditional_map = {k: k for k in analyzers}
conditional_map["Energy optimizer"] = "Energy optimizer"
graph.add_conditional_edges("supervisor", lambda x: x["next"], conditional_map)

graph.add_edge("Energy optimizer", END)

graph.set_entry_point("supervisor")

graph = graph.compile()

config = {"recursion_limit": 10}


def generate_response(input_text):
    output = ""
    for s in graph.stream(
            {
                "messages": [HumanMessage(
                    input_text)]
            }, config=config
    ):
        print(s)
        output = s
    return output['Energy optimizer']['messages'][0].content


def main():
    st.title("Multi-Agenten System")

    user_input = st.text_input("Enter your request:", "")

    if st.button("Generate Response"):
        if user_input:
            with st.spinner("Generating response..."):
                response = generate_response(user_input)
                formatted_text, image_data = format_response(response)

                st.markdown(formatted_text, unsafe_allow_html=True)

                if image_data:
                    image = BytesIO(base64.b64decode(image_data))
                    st.image(image, caption="Generated Plot", use_column_width=True)
        else:
            st.warning("Please enter a request.")


if __name__ == "__main__":
    main()
