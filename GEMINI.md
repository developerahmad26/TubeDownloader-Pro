# Project Rules: TubeDownloader Pro

## 🔄 Automatic Git Synchronization & Push Rule
- **Mandatory Policy**: Whenever ANY change is made to this codebase (code edit, bug fix, feature addition, config update, or documentation), you MUST automatically stage, commit, and push the changes to GitHub (`origin main`) immediately.
- **No User Prompt Needed**: Do not ask the user for permission or wait for them to say "commit karo" or "push karo". Perform the commit and push proactively at the end of every change.
- **Workflow**:
  1. Verify the change works / compiles.
  2. `git add .`
  3. `git commit -m "<Clear, descriptive commit message>"`
  4. `git push origin main`
