提交当前变更并推送

1. 检查当前变更是否都合理
2. commit 所有合理变更，赋予有意义的名字
3. 提交的时候,会触发 pre-commit 检查。如果 pre-commit 提示问题，逐步修复。对于不确定的 issue,请求用户确认。
注意：如果需要提前检查变更，禁止使用 `pre-commit run --all-files`, 只能针对当前提交的文件使用 `pre-commit run --files <file>`
注意： 不可以使用 `--no-verify` 跳过检查,如果有问题，可以提给用户确认。可以建议用户忽略不必要修改的提示，比如针对历史代码跳过放松检查 `# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals`, 甚至建议放松 pre-commit 检查

4. 合并 master 分支, git fetch+git merge origin/master
注意: 如果合并提示冲突,取消 merge 报告给用户。

5. push 到远程仓库
