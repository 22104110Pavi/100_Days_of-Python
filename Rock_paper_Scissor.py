rock = '''
    _______
---'   ____)
      (_____)
      (_____)
      (____)
---.__(___)
'''

paper = '''
    _______
---'   ____)____
          ______)
          _______)
         _______)
---.__________)
'''

scissors = '''
    _______
---'   ____)____
          ______)
       __________)
      (____)
---.__(___)
'''

n=int(input("What would You Choose For Rock Paper and  Scissor.Choose 0->Rock 1->Paper 2->Scissor  "))
list=[rock,paper,scissors]
if n<=2:
  print ("Your Choice is ",list[n])
else:
  print("Choose a number from 0 to 2")

print("Computer's Choice")
import random 
r=random.randint(0,2)
print(list[r])
if n==r:
  print("Its a tie")
elif( (n==0 and r==1) or(n==1 and r==2) or(n==2 and r==0)):
  print("Computer Wins")
else:
  print("You Win ")
