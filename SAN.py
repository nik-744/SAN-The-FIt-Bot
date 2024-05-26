from configparser import ConfigParser
import sys
import google.generativeai as genai
import requests

# Configure the API with the provided API key
genai.configure(api_key="AIzaSyCSryri9Mgo2oqump05gw0NHOYr3FIrml0")

# Define generation configuration
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

# Define safety settings
safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_ONLY_HIGH",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_ONLY_HIGH",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_ONLY_HIGH",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_ONLY_HIGH",
    },
]

# Initialize the model with the correct name and configuration
try:
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro-latest",
        safety_settings=safety_settings,
        generation_config=generation_config,
        system_instruction="You are a Fitness Chat bot named SAN. You should make a diet plan for a personal user. Without asking too many questions, you should prepare a diet plan. Before giving the diet plan, take the height, weight, and age as input, and you should calculate BMI, IBW, and TDEE for the user.",
    )
except Exception as e:
    print(f"Error initializing model: {e}")


# Custom exception for GenAI errors
class GeniAIException(Exception):
    pass


# ChatBot class
class ChatBot:
    CHATBOT_NAME = 'SAN'

    def __init__(self, api_key):
        self.genai = genai
        self.genai.configure(api_key=api_key)
        self.model = model  # Use the globally initialized model
        self.conversation = None
        self._conversation_history = []

    def send_prompt(self, prompt, temperature=0.1):
        if temperature < 0 or temperature > 1:
            raise GeniAIException('Temperature can be between 0 and 1')
        if not prompt:
            raise GeniAIException('Prompt cannot be empty')

        try:
            response = self.conversation.send_message(
                content=prompt,
                generation_config=self._generation_config(temperature),
            )
            response.resolve()
            return f'{response.text}\n' + '___' * 20
        except Exception as e:
            raise GeniAIException(str(e))

    @property
    def history(self):
        conversation_history = [
            {'role': message.role, 'text': message.parts[0].text} for message in self.conversation.history
        ]
        return conversation_history

    def clear_conversation(self):
        self.conversation = self.model.start_chat(history=[])

    def start_conversation(self):
        self.conversation = self.model.start_chat(history=self._conversation_history)

    def _generation_config(self, temperature):
        return genai.types.GenerationConfig(
            temperature=temperature
        )

    def _construct_message(self, text, role='user'):
        return {
            'role': role,
            'parts': [text]
        }

    def preload_conversation(self, conversation_history):
        if isinstance(conversation_history, list):
            self._conversation_history = conversation_history
        else:
            self._conversation_history = [
                self._construct_message(
                    'From now on, return the output as JSON object that can be loaded in Python with the key as \'text\'. For example, {"text": "<output goes here"}'),
                self._construct_message(
                    '{"text": "Sure, I can return the output as a regular JSON object with the key as `text`. Here is the example: {"text": "Your Output"}.',
                    'model')
            ]


# FitnessAgent class
class FitnessAgent:
    def __init__(self, openai_api_key: str, nut_api_key: str):
        self.openai_api_key = openai_api_key
        self.nut_api_key = nut_api_key

    def get_nutritional_info(self, query: str) -> dict:
        """Fetch the nutritional information for a specific food item."""
        api_url = f'https://api.api-ninjas.com/v1/nutrition?query={query}'
        response = requests.get(api_url, timeout=100, headers={'X-Api-Key': self.nut_api_key})

        if response.status_code == requests.codes.ok:
            return response.json()
        else:
            return {"Error": response.status_code, "Message": response.text}

    def calculate_bmi(self, weight: float, height: float) -> float:
        """Calculate the Body Mass Index (BMI) for a person."""
        height_meters = height / 100
        bmi = weight / (height_meters ** 2)
        return round(bmi, 2)

    def calculate_calories_to_lose_weight(self, desired_weight_loss_kg: float) -> float:
        """Calculate the number of calories required to lose a certain amount of weight."""
        calories_per_kg_fat = 7700
        return desired_weight_loss_kg * calories_per_kg_fat

    def calculate_bmr(self, weight: float, height: float, age: int, gender: str,
                      equation: str = 'mifflin_st_jeor') -> float:
        """Calculate the Basal Metabolic Rate (BMR) for a person."""
        if equation.lower() == 'mifflin_st_jeor':
            if gender.lower() == 'male':
                return (10 * weight) + (6.25 * height) - (5 * age) + 5
            else:
                return (10 * weight) + (6.25 * height) - (5 * age) - 161
        else:
            if gender.lower() == 'male':
                return 88.362 + (13.397 * weight) + (4.799 * height) - (5.677 * age)
            else:
                return 447.593 + (9.247 * weight) + (3.098 * height) - (4.330 * age)

    def calculate_tdee(self, bmr: float, activity_level: str) -> float:
        """Calculate the Total Daily Energy Expenditure (TDEE) for a person."""
        activity_factors = {
            '1': 1.2,    # Sedentary
            '2': 1.375,  # Lightly active
            '3': 1.55,   # Moderately active
            '4': 1.725,  # Very active
            '5': 1.9,    # Super active
        }
        return bmr * activity_factors.get(activity_level, 1)

    def calculate_ibw(self, height: float, gender: str) -> float:
        """Calculate the Ideal Body Weight (IBW)."""
        if gender.lower() == 'male':
            if height <= 60:
                return 50
            else:
                return 50 + 2.3 * (height - 60)
        elif gender.lower() == 'female':
            if height <= 60:
                return 45.5
            else:
                return 45.5 + 2.3 * (height - 60)
        else:
            raise ValueError("Invalid gender. Expected 'male' or 'female'.")


def main():
    config = ConfigParser()
    config.read('credentials.ini.txt')
    api_key = config['gemini_ai']['API_KEY']
    nut_api_key = config['nutrition_api']['API_KEY']

    chatbot = ChatBot(api_key=api_key)
    fitness_agent = FitnessAgent(openai_api_key=api_key, nut_api_key=nut_api_key)
    chatbot.start_conversation()

    print("Welcome to SAN, Worlds Most Advanced Fitbot. Type 'quit' to exit. \nInspired By : Chris Bumstead")
    print(
        "We will start by making a Diet plan according to your goal i.e, muscle gain, weight loss, etc. Kindly enter your diet plan and Goal")
    # print(
    #     "Activity levels: \n1. Sedentary \n2. Lightly Active \n3. Moderately Active \n4. Very Active \n5. Super Active")

    while True:
        user_input = input("You: ")
        if user_input.lower() == 'quit':
            sys.exit("SKINNY BITCH")

        try:
            if "diet plan" in user_input.lower() or "muscle gain" in user_input.lower() or "weight loss" in user_input.lower() or "Workout plan" in user_input.lower():
                # Directly parse user input for necessary details
                goal = ""
                if "muscle gain".lower() in user_input.lower() or "gain weight".lower() in user_input.lower():
                    goal = "muscle gain"
                elif "lose weight".lower() in user_input.lower() or "weight loss".lower() in user_input.lower():
                    goal = "weight loss"
                elif "maintain weight".lower() in user_input.lower():
                    goal = "maintain weight"

                print("Please provide the following details:")
                height = float(input("Height (cm): "))
                weight = float(input("Weight (kg): "))
                age = int(input("Age: "))
                gender = input("Gender (male/female): ").lower()
                dietpreference = input("Diet Preference (Veg/Non Veg):").lower()
                print(
                    "Activity levels: \n1. Sedentary \n2. Lightly Active \n3. Moderately Active \n4. Very Active \n5. Super Active")
                activity_level = input("Activity level (choose a number): ").strip()
                days = int(input("Number of days for the diet plan: "))

                # Calculate metrics
                bmi = fitness_agent.calculate_bmi(weight, height)
                bmr = fitness_agent.calculate_bmr(weight, height, age, gender)
                tdee = fitness_agent.calculate_tdee(bmr, activity_level)

                # Prepare a summary to send to the chatbot model
                user_profile = f"""
                User Profile:
                - Height: {height} cm
                - Weight: {weight} kg
                - Age: {age}
                - Gender: {gender}
                - Activity Level: {activity_level}
                - Diet Preference: {dietpreference}
                - Goal: {goal}

                Calculated Metrics:
                - BMI: {bmi}
                - BMR: {bmr} kcal/day
                - TDEE: {tdee} kcal/day
                """

                diet_plan_prompt = f"{user_profile}\n\nBased on the above information, create a detailed {days}-days {dietpreference} diet plan for the user to achieve their goal of {goal}."
                print(f"Bmi : {bmi}")
                print(f"Bmr : {bmr}")
                print(f"TDEE(Total day energy expenditure) : {tdee}")

                response = chatbot.send_prompt(diet_plan_prompt)
                print(f"{chatbot.CHATBOT_NAME}: {response}")

            elif "recipe" in user_input.lower():
                # Extract meal name from user input
                meal_name = user_input.lower().split("recipe for")[1].strip()

                # Prepare prompt to get step-by-step recipe
                recipe_prompt = f"Provide a step-by-step recipe for {meal_name}."

                response = chatbot.send_prompt(recipe_prompt)
                print(f"{chatbot.CHATBOT_NAME}: {response}")

            else:
                response = chatbot.send_prompt(user_input)
                print(f"{chatbot.CHATBOT_NAME}: {response}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
