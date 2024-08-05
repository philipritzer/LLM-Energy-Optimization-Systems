import operator
from datetime import datetime
from typing import Annotated
from typing import Sequence, TypedDict

import requests
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

import auth_keys
import myconfig


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str


def agent_node(state: AgentState, agent: AgentExecutor, name: str):
    result = agent.invoke(state)
    if name == "Energy optimizer":
        return {"messages": [HumanMessage(content=result["output"])]}
    else:
        return {"messages": [HumanMessage(content=name + ' says: \n' + result["output"])]}


def create_agent(llm: ChatOpenAI, tools: list, system_prompt: str):
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt,
            ),
            MessagesPlaceholder(variable_name="messages"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    agent = create_openai_tools_agent(llm, tools, prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        handle_parsing_errors=True
    )
    return executor


@tool("live_data")
def get_live_data():
    """Retrieves live data of the solar system"""
    base_url = myconfig.url_to_raspberry_rest_api

    try:
        response = requests.get(base_url)
        return response.json()
    except:
        return "There was an error retrieving the data."


@tool("summed_historic_data")
def get_summed_historic_data():
    """Retrieves the summed up historic solar data"""
    base_url = myconfig.url_summed_up_data
    response = requests.get(base_url)

    if response.status_code == 200:
        data = response.json()
        output_string = "Energy Historic Data last three days: \n"
        for idx, entry in enumerate(data):
            date = entry['date']
            consumption_positive = entry['consumption_positive']
            grid_negative = entry['grid_negative']
            grid_positive = entry['grid_positive']
            production_positive = entry['production_positive']

            if idx == len(data) - 1:
                date_description = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y") + " (today)"
            else:
                date_description = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")

            entry_string = f"""
    Date: {date_description}
    - Consumption Positive: {consumption_positive}
    - Grid Negative: {grid_negative}
    - Grid Positive: {grid_positive}
    - Production Positive: {production_positive}
        """
            output_string += entry_string
        output_string += ("\n \nGrid Positive is how much was drawn from the grid. \nGrid negative is how much was fed "
                          "into the grid.")

        return output_string
    else:
        return "There was an error retrieving the data."


@tool("energy_optimizer")
def energy_optimizer():
    """Responds with energy optimization methods"""
    return ""


@tool("weather_forecaster")
def get_weather_forecast():
    """Retrieves the current weather and the forecast for the next 3 days."""
    base_url = "https://api.openweathermap.org/data/2.5/forecast/daily"
    params = {
        'lat': '49.300652',
        'lon': '10.571460',
        'appid': auth_keys.openweather_api_key,
        'units': 'metric'
    }

    response = requests.get(base_url, params=params)
    print(response.url)
    if response.status_code == 200:
        data = response.json()
        # print(json.dumps(data, indent=4))
        export_data = {}
        for i in range(4):
            export_data[i] = {
                "date": data["list"][i]["dt"],
                "temp": data["list"][i]["temp"]["day"],
                "weather": data["list"][i]["weather"][0]["main"],
                "clouds": data["list"][i]["clouds"],
            }

        output_string = f"""
Weather Forecast
Today's Forecast:
Date: {datetime.utcfromtimestamp(data["list"][0]["dt"]).strftime('%Y-%m-%d')}
Temperature: {export_data[0]["temp"]} °C
Weather: {export_data[0]["weather"]}
Cloud Coverage: {export_data[0]["clouds"]}%

Next 3 Days:
Day 1 - {datetime.utcfromtimestamp(data["list"][1]["dt"]).strftime('%Y-%m-%d')}
Temperature: {export_data[1]["temp"]} °C
Weather: {export_data[1]["weather"]}
Cloud Coverage: {export_data[1]["clouds"]}%

Day 2 - {datetime.utcfromtimestamp(data["list"][2]["dt"]).strftime('%Y-%m-%d')}
Temperature: {export_data[2]["temp"]} °C
Weather: {export_data[2]["weather"]}
Cloud Coverage: {export_data[2]["clouds"]}%

Day 3 - {datetime.utcfromtimestamp(data["list"][3]["dt"]).strftime('%Y-%m-%d')}
Temperature: {export_data[3]["temp"]} °C
Weather: {export_data[3]["weather"]}
Cloud Coverage: {export_data[3]["clouds"]}%
"""
        return output_string
    else:
        return "There was an error retrieving the data."


def weather_state_update(state: AgentState, agent: AgentExecutor, name: str):
    print("weather_state_update called")
    result = agent.invoke(state)

    updated_content = (
        f"{state.get('messages')[0].content}\n"
        "____additional information____\n\n"
        f"{result['output']}\n"
        "The data has successfully been retrieved."
    )

    return {
        "messages": [HumanMessage(content=updated_content)],
        "next": "supervisor",
        "intermediate_steps": [(name, str(result))]
    }


def format_response(response):
    if isinstance(response, dict):
        text_output = response.get('text', '')
        image_data = response.get('image', None)

        formatted_text = f"""
        {text_output}
        """

        return formatted_text, image_data
    else:
        return response, None
