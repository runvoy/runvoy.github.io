"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const core = __importStar(require("@actions/core"));
const github = __importStar(require("@actions/github"));
async function run() {
    try {
        const token = core.getInput('token', { required: true });
        const environment = core.getInput('environment', { required: true });
        const keepCount = parseInt(core.getInput('keep_count') || '10', 10);
        const excludeDeploymentId = core.getInput('exclude_deployment_id') || '';
        const excludeMostRecent = core.getBooleanInput('exclude_most_recent') || false;
        const octokit = github.getOctokit(token);
        const context = github.context;
        core.info(`Fetching deployments for environment: ${environment}`);
        core.info(`Keeping the last ${keepCount} deployments`);
        // Fetch all deployments for the environment
        const { data: deployments } = await octokit.rest.repos.listDeployments({
            owner: context.repo.owner,
            repo: context.repo.repo,
            environment: environment,
            per_page: 100, // Maximum per page
        });
        if (deployments.length === 0) {
            core.info('No deployments found. Nothing to clean up.');
            return;
        }
        core.info(`Found ${deployments.length} deployment(s)`);
        // Sort by creation date (newest first) to identify the most recent
        const sortedDeployments = [...deployments].sort((a, b) => {
            const dateA = new Date(a.created_at).getTime();
            const dateB = new Date(b.created_at).getTime();
            return dateB - dateA;
        });
        // Determine which deployment ID to exclude
        let deploymentIdToExclude = null;
        if (excludeDeploymentId) {
            deploymentIdToExclude = parseInt(excludeDeploymentId, 10);
            core.info(`Excluding specified deployment ID: ${deploymentIdToExclude}`);
        }
        else if (excludeMostRecent && sortedDeployments.length > 0) {
            deploymentIdToExclude = sortedDeployments[0].id;
            core.info(`Excluding most recent deployment ID: ${deploymentIdToExclude} (created: ${sortedDeployments[0].created_at})`);
        }
        // Filter out the excluded deployment if specified
        let deploymentsToProcess = deployments;
        if (deploymentIdToExclude !== null) {
            deploymentsToProcess = deployments.filter(d => d.id !== deploymentIdToExclude);
            if (deploymentsToProcess.length < deployments.length) {
                core.info(`Excluded deployment from cleanup, processing ${deploymentsToProcess.length} deployment(s)`);
            }
        }
        // Sort by creation date (newest first) - deploymentsToProcess may already be sorted, but ensure it
        deploymentsToProcess.sort((a, b) => {
            const dateA = new Date(a.created_at).getTime();
            const dateB = new Date(b.created_at).getTime();
            return dateB - dateA;
        });
        // Keep only the last N deployments
        const deploymentsToDelete = deploymentsToProcess.slice(keepCount);
        if (deploymentsToDelete.length === 0) {
            core.info(`Only ${deploymentsToProcess.length} deployment(s) found. No cleanup needed.`);
            return;
        }
        core.info(`Deleting ${deploymentsToDelete.length} old deployment(s)...`);
        // Delete old deployments
        let deletedCount = 0;
        let errorCount = 0;
        for (const deployment of deploymentsToDelete) {
            try {
                await octokit.rest.repos.deleteDeployment({
                    owner: context.repo.owner,
                    repo: context.repo.repo,
                    deployment_id: deployment.id,
                });
                core.info(`✓ Deleted deployment ID: ${deployment.id} (created: ${deployment.created_at})`);
                deletedCount++;
            }
            catch (error) {
                const errorMessage = error instanceof Error ? error.message : String(error);
                core.warning(`✗ Failed to delete deployment ID ${deployment.id}: ${errorMessage}`);
                errorCount++;
            }
        }
        core.info(`\nCleanup complete!`);
        core.info(`  - Deleted: ${deletedCount} deployment(s)`);
        if (errorCount > 0) {
            core.warning(`  - Errors: ${errorCount} deployment(s) failed to delete`);
        }
        core.info(`  - Kept: ${Math.min(keepCount, deploymentsToProcess.length)} deployment(s)`);
    }
    catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        core.setFailed(`Action failed with error: ${errorMessage}`);
    }
}
run();
