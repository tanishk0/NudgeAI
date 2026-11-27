# Presentation: an agent that can explain its repair

## A six-minute demonstration

1. **Problem (45 seconds).** Show Nudge's project brief. Explain the difference between an assistant that suggests code and an agent that acts, observes, and verifies. Name SWE-agent/mini-swe-agent as the open-source reference and show the pinned commit.
2. **Learning workflow (60 seconds).** Open the 16-task plan. Pick the model parser or completion task. Show its specification, criteria, and a mentor nudge. Explain that Nudge teaches the machinery rather than handing over a finished agent.
3. **One implementation (60 seconds).** Implement a small prepared function, such as the first-line completion marker. Run Check task. Explain why a marker buried in logs or a failed shell command cannot submit.
4. **Repair experiment (90 seconds).** Use a separate, previously completed rehearsal workspace/export. Run → Preview → Run the repair experiment. Show the initial failing tests, source inspection, the addition patch, passing tests, and final submission. The responses are scripted for reproducibility; do not call this a live reasoning demonstration.
5. **Evidence (60 seconds).** Show trajectory roles, call/cost counters, the diff, and independent final test output. Explain that Submitted does not imply Verified.
6. **Engineering (45 seconds).** Explain the outer Docker boundary, bounded steps/cost, process-group timeouts, persistence, and model/environment interfaces.

## Rehearsal checklist

- Start Docker and build Nudge's runtime image before the session; do not rely on installing packages on stage.
- Sign in and load the project before presenting. Start the preview shortly before demonstrating it; previews expire after ten minutes.
- Complete the course in a rehearsal account/workspace or export. Keep a checkpoint before the one function you plan to implement live. Do not reset the only completed workspace.
- For a prepared Nudge rehearsal workspace, use a separate account, open this project, and copy the six completed learner modules from the instructor ZIP into its matching files. Save a checkpoint. ZIP import is not implemented; the export does not automatically complete a learner workspace or grant task passes. Run the checks normally.
- Use a clean browser window and test the projector dimensions. Expand Preview when showing the repair.
- Keep a saved recording or exported JSON trajectory as a backup, labelled as a prior run rather than live output.
- The learner's code must be implemented before the full experiment can succeed. The public starter is intentionally incomplete.

## Questions you should be able to answer

- **Is it the real repository?** Pinned real upstream core files are included for reading; the executable lab is an explicit teaching adaptation. It does not claim upstream benchmark performance or implement every upstream feature.
- **Is the model live?** No. The fixture uses a deterministic adapter. The same query boundary can support a real provider later; a production provider integration is outside this course.
- **What is real here?** The agent loop, bash execution, file modification, tests, timeout handling, accounting, and trajectory persistence are real. The suggested actions and their costs are scripted.
- **Why not run bash on the API server?** The learner's environment is a separate network-disabled Docker container. A subprocess by itself is not an isolation boundary.
- **How do you know the repair worked?** Independent tests run after submission; the model's answer is not the success oracle. This tiny fixture is a functional demonstration, not evidence of general coding-agent capability.
- **What did we build?** Nudge's learning workflow and this teaching implementation. Credit the upstream authors for the reference architecture and retain the bundled MIT notice.
