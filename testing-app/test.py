class Dog:
    def __init__(self, name, age, color):
        self.name = name
        self.age = age
        self.color = color

    def bark(self):
        return f"{self.name} says Woof! i am {self.age} years old and I am {self.color}."

# Create instance
my_dog = Dog("Frieda", 3, "white")
print(my_dog.bark()) # Frieda says Woof! i am 3 years old and I am white.
