1
SENG 371 – Spring 2026
Assignment – Change Implementation
This group assignment explores the evolution of an open source software system. By the end of this assignment, you
will:
• Start from a previously validated, real existing issue from an open source software issue tracker;
• Thoroughly understand the issue and design change steps to solve it;
• Code a medium-sized change to a software system using an IDE;
• Submit the result of your changes by means of a pull request to an open source software repository.
Start from a previously validated issue
In the previous step of this assignment (Change Proposal), your lab instructor used the information from your group
submission to assess your change proposal of a medium-sized issue. They looked at the risks and benefits of the chosen
project and issue and provided you with an assessment of the proposed change. If the assessment asserted that the
chosen issue was appropriate, your group may now proceed to solve that issue.
On the other hand, if the assessment asserted that the chosen issue was not appropriate, your group must choose
another issue and contact the lab instructor afterwards to assess it. If you fail to discuss that new issue with your lab
instructor, you may still submit your change implementation up to the due date, but recall that you will still be assessed
under the expectation of solving a medium-sized issue.
Recall: The issue must be medium-sized, i.e., neither too simple nor too complex: that means an issue that affects
more than one production code file (in the OSP’s main programming language) and that may be solved by your group
in about one month (think of something that takes around 16 hours of your individual time, or 64 hours of your group’s
time); typical medium-sized issues affect between two and four production code files (test files not included).
Study the issue and design the change
With the forked repository from the previous step (change proposal), you will have already located the concepts and
analyzed the impact of the issue.
Now, you will thoroughly review the issue and design a change strategy. That strategy means how you will handle the
issue, whether you will split its solving into different steps and how you will split the solving process among the team
members. We strongly suggest that you work in pairs or with the full group during the solving process. Nonetheless,
it is up to your group to decide how you will work.
Of course, you may interact with the open source software team by using the issue URL to ask questions and clear
doubts about it (open source teams are made of volunteers that are generally busy persons that may or may not answer
your questions and comments, so please do not rely on this as a strategy for problem solving; but as you may see from
some issues, they sometimes answer questions and help newcomers).
Actualization
You will code your changes in your forked public repository. Before you start changing code, create a branch and
checkout the new branch, so that you do not work on the main branch during your issue solving.
Your team must perform the changes in the source code in order to solve the issue. Other group members may help
with suggestions. We suggest that your team works with pair programming (either local or remote pair programming)
2
because the type of communication that pair programming requires usually leads to deeper learning and better coding
choices.
You may commit parts of your change into your branch, before you submit the full change to the main open source
software system repository. This may be useful because you may split your change into smaller steps.
Submit a pull request to the open source software repository
After your group finishes coding the solution for the issue, submit a pull request back into the main branch of the
public original open source software repository.
After you submit your pull request, let the grader know that the issue has been solved, so he may start grading.
Assessment
The pull request will be assessed by your grader. He will then analyze the changes in the pull request.
Since this is a group assignment, one of the group members will submit (via Brightspace until the assignment deadline)
an assessment how the group solved the issue (as a PDF document), with the following information:
1. Basic information for each group member:
a. Full name;
b. UVic email;
c. GitHub ID;
2. A short description of the OSP project (e.g., what it does, its domain, code size, main programming language,
number of active contributors) and the reason why your group chose that project;
3. A web link to the original OSP repository on GitHub;
4. A web link to the forked repository on GitHub that your group is using;
5. A web link to the issue in the original OSP issue tracker on GitHub (with the information that the issue is
assigned to one of your group members);
6. A description of the chosen issue, and the reason why your group picked that issue to solve;
7. The result of your concept location;
8. The result of your impact analysis;
9. The change strategy your group designed to solve the issue (one or two paragraphs);
10. A web link of your group’s pull request into the original OSP repository on GitHub;
11. An analysis of the difference between your previous impact analysis and the effective change performed (one
or two paragraphs).
12. A short description (one or two paragraphs) of the pros and cons of this experience of changing a real open
source software system.
Items from 1 to 8 might be the same as in the previous assignment (change proposal) in case your proposal had been
fully accepted as appropriate by your grader. Otherwise, provide new information from the effective new issue you
solved. On the other hand, items 9 to 12 are new to this assignment and should describe your solution.
Your grader, then, will use the information from the group submission to assess your group’s work.
Your grader may also assign bonus points (up to 20% of the maximum change implementation grade) to a pull request
that has been accepted by the open source community (up to April 3, 2026).
3
Grading rubric
• 20 marks - well-explained solving strategy so that the grader can understand how it aligns with your code
implementation
- The change strategy your group designed to solve the issue (one or two paragraphs).
• 60 marks - pull request
- 10 marks for code documentation
- 10 marks for testing (either manual or automated; if manual, please add details inside the pull
request)
- 40 marks for production code (e.g., code is clear, solves the issue, good commit messages)
- A web link of your group’s pull request into the original OSP repository on GitHub.
• 10 marks - impact analysis vs. change implementation
- An analysis of the difference between your previous impact analysis and the effective change
performed (one or two paragraphs).
• 10 marks - pros and cons of this experience
- A short description (one or two paragraphs) of the pros and cons of this experience of changing a
real open source software system.
• 20 extra marks - Your lab instructor may also assign bonus points (up to 20% of the maximum change
implementation grade) to a pull request that has been accepted by the open source community (up to April 4,
2025).